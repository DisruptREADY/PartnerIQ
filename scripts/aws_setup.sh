#!/usr/bin/env bash
# PartnerIQ — one-shot AWS infrastructure setup
# Requires: aws cli v2, jq
# Run: bash scripts/aws_setup.sh
set -e

REGION="us-east-1"
BUCKET="partneriq-frontend"
LAMBDA_NAME="partneriq-api"
API_NAME="partneriq-api"
CF_COMMENT="PartnerIQ frontend distribution"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   PartnerIQ — AWS Setup Script       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Collect secrets ──────────────────────────────────────────────────────────
read -p "AUTH0_DOMAIN (e.g. disruptready.us.auth0.com): " AUTH0_DOMAIN
read -p "AUTH0_AUDIENCE (e.g. https://partneriq.api): " AUTH0_AUDIENCE
read -p "ALLOWED_ORIGINS (e.g. https://partneriq.pellerintechnology.com,http://localhost:5173): " ALLOWED_ORIGINS

# Trim leading/trailing whitespace from all inputs
AUTH0_DOMAIN="${AUTH0_DOMAIN// /}"
AUTH0_AUDIENCE="${AUTH0_AUDIENCE// /}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS## }"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS%% }"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo ""
echo "→ AWS Account: $ACCOUNT_ID  |  Region: $REGION"
echo ""

# ── 1. S3 Bucket ─────────────────────────────────────────────────────────────
echo "[1/6] Creating S3 bucket: $BUCKET"
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null || echo "  (bucket already exists)"

aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo "  ✓ S3 bucket ready"

# ── 2. Lambda IAM Role ────────────────────────────────────────────────────────
echo "[2/6] Creating Lambda IAM role"
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

ROLE_ARN=$(aws iam create-role \
  --role-name partneriq-lambda-role \
  --assume-role-policy-document "$TRUST" \
  --query Role.Arn --output text 2>/dev/null || \
  aws iam get-role --role-name partneriq-lambda-role --query Role.Arn --output text)

aws iam attach-role-policy \
  --role-name partneriq-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

echo "  ✓ IAM role: $ROLE_ARN"
echo "  Waiting 10s for role to propagate..."
sleep 10

# ── 3. Build & package Lambda ─────────────────────────────────────────────────
echo "[3/6] Building Lambda package"
rm -rf /tmp/partneriq-lambda && mkdir /tmp/partneriq-lambda
pip3 install -r requirements.txt --target /tmp/partneriq-lambda -q
cp -r backend /tmp/partneriq-lambda/backend
cd /tmp/partneriq-lambda && zip -r /tmp/lambda.zip . -q && cd -
echo "  ✓ lambda.zip ready ($(du -sh /tmp/lambda.zip | cut -f1))"

# ── 4. Create or update Lambda function ──────────────────────────────────────
echo "[4/6] Deploying Lambda function: $LAMBDA_NAME"
LAMBDA_ARN=$(aws lambda get-function --function-name "$LAMBDA_NAME" \
  --query Configuration.FunctionArn --output text 2>/dev/null || echo "")

# Write env vars to a JSON file — avoids comma-parsing issues with shorthand
cat > /tmp/lambda-env.json <<JSON
{
  "Variables": {
    "AUTH0_DOMAIN": "$AUTH0_DOMAIN",
    "AUTH0_AUDIENCE": "$AUTH0_AUDIENCE",
    "ALLOWED_ORIGINS": "$ALLOWED_ORIGINS"
  }
}
JSON

if [ -z "$LAMBDA_ARN" ]; then
  LAMBDA_ARN=$(aws lambda create-function \
    --function-name "$LAMBDA_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler backend.main.handler \
    --zip-file fileb:///tmp/lambda.zip \
    --timeout 30 \
    --memory-size 512 \
    --environment file:///tmp/lambda-env.json \
    --query FunctionArn --output text)
  echo "  ✓ Lambda created"
else
  aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --zip-file fileb:///tmp/lambda.zip --output text > /dev/null
  sleep 5
  aws lambda update-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --environment file:///tmp/lambda-env.json --output text > /dev/null
  echo "  ✓ Lambda updated"
fi

# ── 5. API Gateway ────────────────────────────────────────────────────────────
echo "[5/6] Creating API Gateway: $API_NAME"
API_ID=$(aws apigatewayv2 get-apis \
  --query "Items[?Name=='$API_NAME'].ApiId" --output text 2>/dev/null || echo "")

# Build CORS JSON from ALLOWED_ORIGINS (handles comma-separated list)
IFS=',' read -ra ORIGIN_ARRAY <<< "$ALLOWED_ORIGINS"
ORIGINS_JSON=$(printf '"%s",' "${ORIGIN_ARRAY[@]}" | sed 's/,$//')
CORS_JSON="{\"AllowOrigins\":[$ORIGINS_JSON],\"AllowMethods\":[\"GET\",\"POST\",\"PUT\",\"DELETE\",\"OPTIONS\"],\"AllowHeaders\":[\"Content-Type\",\"Authorization\"],\"MaxAge\":86400}"

if [ -z "$API_ID" ]; then
  API_ID=$(aws apigatewayv2 create-api \
    --name "$API_NAME" \
    --protocol-type HTTP \
    --cors-configuration "$CORS_JSON" \
    --query ApiId --output text)
  echo "  ✓ API created: $API_ID"
else
  aws apigatewayv2 update-api --api-id "$API_ID" \
    --cors-configuration "$CORS_JSON" --output text > /dev/null
  echo "  ✓ API already exists: $API_ID (CORS updated)"
fi

# Lambda permission (idempotent)
aws lambda add-permission \
  --function-name "$LAMBDA_NAME" \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*" \
  --output text > /dev/null 2>&1 || true

# Integration — always ensure one exists
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id "$API_ID" \
  --query "Items[0].IntegrationId" --output text 2>/dev/null || echo "")

if [ -z "$INTEGRATION_ID" ] || [ "$INTEGRATION_ID" = "None" ]; then
  INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "$API_ID" \
    --integration-type AWS_PROXY \
    --integration-uri "arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$LAMBDA_NAME" \
    --payload-format-version "2.0" \
    --query IntegrationId --output text)
  echo "  ✓ Integration created: $INTEGRATION_ID"
fi

# Route — ensure ANY /{proxy+} is wired to the integration
ROUTE_ID=$(aws apigatewayv2 get-routes --api-id "$API_ID" \
  --query "Items[?RouteKey=='ANY /{proxy+}'].RouteId" --output text 2>/dev/null || echo "")

if [ -z "$ROUTE_ID" ] || [ "$ROUTE_ID" = "None" ]; then
  aws apigatewayv2 create-route \
    --api-id "$API_ID" \
    --route-key "ANY /{proxy+}" \
    --target "integrations/$INTEGRATION_ID" --output text > /dev/null
else
  aws apigatewayv2 update-route \
    --api-id "$API_ID" --route-id "$ROUTE_ID" \
    --target "integrations/$INTEGRATION_ID" --output text > /dev/null
fi

# Stage
aws apigatewayv2 create-stage \
  --api-id "$API_ID" \
  --stage-name '$default' \
  --auto-deploy --output text > /dev/null 2>&1 || true

API_URL="https://$API_ID.execute-api.$REGION.amazonaws.com"
echo "  ✓ API Gateway URL: $API_URL"

# ── 6. CloudFront Distribution ────────────────────────────────────────────────
echo "[6/6] Creating CloudFront distribution"
CF_CONFIG=$(cat <<JSON
{
  "Comment": "$CF_COMMENT",
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "s3-partneriq",
      "DomainName": "$BUCKET.s3.$REGION.amazonaws.com",
      "S3OriginConfig": { "OriginAccessIdentity": "" }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-partneriq",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "AllowedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] },
    "Compress": true
  },
  "CustomErrorResponses": {
    "Quantity": 1,
    "Items": [{
      "ErrorCode": 403,
      "ResponseCode": "200",
      "ResponsePagePath": "/index.html",
      "ErrorCachingMinTTL": 0
    }]
  },
  "Enabled": true,
  "HttpVersion": "http2"
}
JSON
)

CF_RESULT=$(aws cloudfront create-distribution \
  --distribution-config "$CF_CONFIG" \
  --query "[Distribution.Id, Distribution.DomainName]" \
  --output text 2>/dev/null || echo "EXISTS EXISTS")

CF_ID=$(echo $CF_RESULT | awk '{print $1}')
CF_DOMAIN=$(echo $CF_RESULT | awk '{print $2}')

if [ "$CF_ID" = "EXISTS" ]; then
  echo "  (CloudFront distribution already exists — check AWS console for domain)"
else
  echo "  ✓ CloudFront ID: $CF_ID"
  echo "  ✓ CloudFront domain: $CF_DOMAIN"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  DONE — Add these to GitHub Secrets                         ║"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║  %-30s  %-28s ║\n" "AWS_ACCESS_KEY_ID" "(your IAM key)"
printf "║  %-30s  %-28s ║\n" "AWS_SECRET_ACCESS_KEY" "(your IAM secret)"
printf "║  %-30s  %-28s ║\n" "S3_BUCKET" "$BUCKET"
printf "║  %-30s  %-28s ║\n" "CLOUDFRONT_DISTRIBUTION_ID" "${CF_ID:-check console}"
printf "║  %-30s  %-28s ║\n" "VITE_AUTH0_DOMAIN" "$AUTH0_DOMAIN"
printf "║  %-30s  %-28s ║\n" "VITE_AUTH0_CLIENT_ID" "0VGV76JCzrAjJXNbOhce2o8LHHNbiBsX"
printf "║  %-30s  %-28s ║\n" "VITE_AUTH0_AUDIENCE" "$AUTH0_AUDIENCE"
echo "╠══════════════════════════════════════════════════════════════╣"
printf "║  %-30s  %-28s ║\n" "API Gateway URL" "$API_URL"
printf "║  %-30s  %-28s ║\n" "CloudFront domain" "${CF_DOMAIN:-check console}"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Cloudflare DNS → CNAME  partneriq  →  ${CF_DOMAIN:-<cloudfront domain>}"
echo ""

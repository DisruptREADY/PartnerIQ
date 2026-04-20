/**
 * Shared Chart.js configuration — registers only needed components for tree-shaking
 * and sets global defaults for font family, tooltip styling, and brand consistency.
 * Import this module instead of calling Chart.register() directly.
 *
 * Only bar + line chart types are used; importing specific components instead of
 * `registerables` saves ~40-55KB in the production bundle.
 */
import {
  Chart,
  LineController,
  BarController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

Chart.register(
  LineController,
  BarController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

// Typography — match the app's Corbel body font
const fontFamily = "Corbel, 'Lucida Grande', 'Lucida Sans Unicode', -apple-system, sans-serif";
Chart.defaults.font.family = fontFamily;
Chart.defaults.font.size = 12;

// Tooltip branding
Chart.defaults.plugins.tooltip.backgroundColor = '#15123E';
Chart.defaults.plugins.tooltip.titleColor = '#FFFFFF';
Chart.defaults.plugins.tooltip.bodyColor = '#FFFFFF';
Chart.defaults.plugins.tooltip.titleFont = { weight: '600', family: fontFamily };
Chart.defaults.plugins.tooltip.bodyFont = { family: fontFamily };
Chart.defaults.plugins.tooltip.cornerRadius = 6;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.boxPadding = 4;

// Legend font
Chart.defaults.plugins.legend.labels.font = { family: fontFamily, size: 12 };

export { Chart };

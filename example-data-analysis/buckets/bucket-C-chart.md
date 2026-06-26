<!-- Bucket Streaming v1.0 -->
<!-- File: bucket-C-chart.md -->
<!-- SELF-CHECK: If you see this line without upstream bucket output, STOP and request upstream. -->

# Bucket C: Chart

## Chart Selection Rules

| Data Type | Recommended Chart |
|---|---|
| Time series | Line chart |
| Comparison | Bar chart |
| Distribution | Histogram / Box plot |
| Composition | Pie chart / Stacked bar |
| Correlation | Scatter plot |

## Chart Configuration

1. Select chart type based on summary themes
2. Configure axes, labels, colors
3. Generate chart description (for AI to render)

## Output Format

```
📈 Chart

Type: [chart type]
Title: [chart title]
X-axis: [label]
Y-axis: [label]
Data series: [description of what's plotted]
Key takeaway: [what the chart shows]

→ Handoff: export
```

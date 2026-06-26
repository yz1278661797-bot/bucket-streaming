<!-- Bucket Streaming v1.0 -->
<!-- File: bucket-A-search.md -->
<!-- SELF-CHECK: If you see this line without upstream bucket output, STOP and request upstream. -->

# Bucket A: Data Search

## Search Strategy

1. Parse user's data request — identify data sources, date ranges, filters
2. Generate search queries from the request
3. Execute queries and collect raw results

## Query Generation Rules

- Transform natural language into structured queries
- Include date ranges when user specifies time periods
- Apply filters to narrow results

## Output Format

After completing search, output:

```
📊 Search Results

Query: [user's request reformulated]
Sources searched: [list of sources]
Results found: [count]
Key data points:
  - [point 1]
  - [point 2]
  - [point 3]
  ...

→ Handoff: summarize
```

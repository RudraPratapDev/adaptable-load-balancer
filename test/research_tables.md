# Research Data Tables

Generated on Thu Feb 19 22:13:53 2026

### Table 5.1 – Failure Resilience Metrics
| Strategy            |   Hit % |   Miss % |   Server Down % |   Timeout % |
|:--------------------|--------:|---------:|----------------:|------------:|
| Round Robin         |   61.26 |    24.2  |            0.06 |       10.76 |
| Least Connections   |   15.46 |     7.72 |            0.1  |        2.3  |
| Least Response Time |   16.72 |     1.3  |            0.26 |        8.06 |
| AURA                |   57.84 |    19.12 |            0.2  |       11.38 |

### Table 5.2 – Tail Latency Metrics
| Strategy            |   P50 |    P95 |     P99 |   P99.9 |
|:--------------------|------:|-------:|--------:|--------:|
| Round Robin         | 45.91 | 359.72 | 1380.57 | 2894.36 |
| Least Connections   |  0    | 236.95 |  394.81 | 1705.77 |
| Least Response Time | 17.92 | 236.14 |  706.78 | 1346.16 |
| AURA                | 41.98 | 353.85 | 1172.07 | 2388.04 |

### Table 5.3 – Burst Handling Metrics
| Strategy            |   Peak Latency | Recovery Time (ms)   |   Variance |
|:--------------------|---------------:|:---------------------|-----------:|
| Round Robin         |        4082.42 | 1757.63 (P99.9)      |    43475.7 |
| Least Connections   |        4031.95 | 1716.59 (P99.9)      |    41516.9 |
| Least Response Time |        5092.49 | 1732.22 (P99.9)      |    20954.2 |
| HELIOS              |        1881.75 | 1738.71 (P99.9)      |    22742.9 |

### Table 5.4 – Cache Performance
| Strategy            |   Hit Rate % |   Miss % |   Avg Latency (Hit) |   Avg Latency (Miss) |
|:--------------------|-------------:|---------:|--------------------:|---------------------:|
| Round Robin         |        87.68 |     1.56 |               39.45 |               236.05 |
| Least Connections   |        51.84 |     1.28 |               38.13 |               235.43 |
| Least Response Time |        52.02 |     0.24 |               83.54 |               235.86 |
| HELIOS              |        46.78 |     0.68 |               53.26 |               236.13 |

### Table 5.5 – Overall Improvement Over Round Robin
| Metric             | AURA Improvement   | HELIOS Improvement   |
|:-------------------|:-------------------|:---------------------|
| P99 Reduction      | 15.1%              | --                   |
| Timeout Reduction  | -5.8%              | --                   |
| Cache Hit Increase | --                 | +-40.9%              |


# Label Decoder: evaluation report

Test set: 100 Indian products from Open Food Facts (photos + structured data).

## Rules layer (deterministic)

- Decoded twice, outputs differed: **0**
- Products with sugar under 2+ names: **21** (21.0%)
- Median teaspoons of sugar per serve: **0.7**

| Flag | Products |
|---|---|
| SAT_FAT_HIGH | 26 |
| SUGAR_SPLIT | 21 |
| SERVING_TINY | 19 |
| SODIUM_HIGH | 10 |
| WHO_LIMIT_HALF | 6 |
| TRANS_FAT | 3 |
| WHO_LIMIT_BLOWN | 2 |
| PER100_VS_SERVE | 1 |
| NAS_HIGH_INTRINSIC | 1 |
| CHOLESTEROL_FREE_PLANT | 1 |
| NAS_SUBSTITUTE | 1 |

### Top 15 by sugar

| Brand | Product | Sugar % | tsp/serve | Sugar names | Flags |
|---|---|---|---|---|---|
| Parle | Parle Mazelo Candy | 79.7 | 0.8 | 2 | SUGAR_SPLIT, SERVING_TINY |
| Cadbury | Shots | 71.9 | 3.2 | 3 | SUGAR_SPLIT, SERVING_TINY, SAT_FAT_HIGH |
| what's up | what's up eye health zeaxanthin & lutein gummies | 66.5 | 0.6 | 2 | SUGAR_SPLIT, SERVING_TINY |
| Nature's Choice | Arabian  DATES | 65.0 | 4.9 | 0 |  |
| Hershey's | HERSHEY'S SYRUP 623g | 63.7 | 4.8 | 4 | SUGAR_SPLIT, WHO_LIMIT_HALF |
| Ashok | Thandaai Masala Powder | 59.8 | 4.5 | 1 | WHO_LIMIT_HALF |
| Nestlé | KitKat Chunky Caramel | 54.6 | 5.7 | 5 | SUGAR_SPLIT, SERVING_TINY, SAT_FAT_HIGH |
| Boni | Mélange de bonbons | 51.8 | 3.9 | 1 |  |
| ProV | Raisins | 47.8 | 3.6 | 0 |  |
| Horlicks | Horlicks Classic Malt | 46.0 | 3.5 | 1 |  |
| Abbott | Similac Plus | 41.0 | 3.1 | 2 | SUGAR_SPLIT, SAT_FAT_HIGH |
| Britannia | Treat Vanilla Creme | 38.4 | 2.9 | 4 | SUGAR_SPLIT |
| KitKat, Nestle nutrition | Kitkat mini chocolate coated wafer | 35.1 | 1.0 | 1 | SERVING_TINY, SAT_FAT_HIGH |
| Farmley | Farmley Date Bites | 33.7 | 1.5 | 1 |  |
| Too Yumm | Too yumm | 32.4 | 1.4 | 2 | SUGAR_SPLIT |

## Extraction accuracy (vision model vs reference)

- Products scored: **98** (errors: 0)
- Field accuracy overall: **87.3%** (tolerance max(0.5, 10%))
- Sugar alias recall: **91.0%**
- Serving size accuracy: **68.8%**

| Field | Accuracy % |
|---|---|
| energy_kcal | 91.8 |
| protein_g | 89.4 |
| carbohydrate_g | 93.8 |
| total_sugars_g | 88.8 |
| dietary_fibre_g | 65.3 |
| total_fat_g | 91.5 |
| saturated_fat_g | 87.5 |
| sodium_mg | 78.0 |

### Where it breaks

| Condition | Accuracy % | Fields |
|---|---|---|
| untagged | 87.3 | 700 |

| Image resolution | Accuracy % | Fields |
|---|---|---|
| 400-800px | 87.3 | 700 |

| Legibility (model's own verdict) | Accuracy % | Fields |
|---|---|---|
| partial | 82.2 | 286 |
| poor | 65.8 | 73 |
| good | 96.2 | 341 |

| Label language | Accuracy % | Fields |
|---|---|---|
| en | 86.2 | 616 |
| multilingual | 95.2 | 84 |

### Worst 10 products

| Barcode | Product | Correct/Scored | Condition | Legibility |
|---|---|---|---|---|
| 8901552023450 | Chana Pulao | 0/8 | untagged | partial |
| 8901725000899 | Multi -Millet Mix | 0/8 | untagged | poor |
| 4906426980222 | instant popcorn | 0/8 | untagged | poor |
| 8904043553085 | Wow Pav | 0/8 | untagged | partial |
| 8901262202046 | Amul Lassi | 0/6 | untagged | partial |
| 8908001588560 | Wheat Chapati | 2/8 | untagged | partial |
| 8908002105087 | Milk White Bread | 4/7 | untagged | partial |
| 89002940 | Coconut oil | 5/8 | untagged | partial |
| 8908014814076 | Premium Burger Buns | 5/8 | untagged | partial |
| 8901030837616 | Chokissimo Choco Brownie | 5/8 | untagged | poor |

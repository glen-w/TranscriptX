# Name gazetteer attribution

Bundled `given_names.json` and `surnames.json` are derived from public-domain
and CC0 sources. Rebuild with `python scripts/data/build_name_gazetteer.py`.

| Source | License | Use |
|--------|---------|-----|
| [sigpwned/popular-names-by-country-dataset](https://github.com/sigpwned/popular-names-by-country-dataset) v1.2 | CC0-1.0 | International forenames and surnames |
| [Hadley Wickham baby-names](https://github.com/hadley/data-baby-names) (SSA national data) | Public domain (US government) | Given names |
| [FiveThirtyEight most-common-name surnames](https://github.com/fivethirtyeight/data/tree/master/most-common-name) (US Census) | Public domain (US government) | Surnames |

These lists are not identity verification. Uncommon names can still pass via
NER roster clustering, hybrid escape, or an optional Twenty CRM match.

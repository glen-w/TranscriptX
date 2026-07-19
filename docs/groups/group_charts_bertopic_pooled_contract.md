Type: CONTRACT
Authority: self

# Group charts — bertopic pooled

- **`bertopic_pooled`** from `aggregate_bertopic_group`, after a **group-level BERTopic refit** on merged preprocessed **source segments** from all transcripts (not joined transcript topic IDs).
- Chart: `group.bertopic.pooled.topic_share.global` — bar of document-topic shares for non-outlier topics.
- Fail closed without non-outlier topics / when `all_outlier` is true (emit **no** chart specification).
- Aggregation registry: `agg_id=bertopic`, `selector=any_of(["bertopic"])`, `deps=[]`.

# Quarantined tests

Quarantined tests are temporarily excluded from Gate B. Each quarantined test
must include a reason, owner/module, and remove_by milestone/date on the same
line as the marker, for example:

```
@pytest.mark.quarantined  # reason: flaky on windows owner: pipeline remove_by: v0.1.1
```

The baseline quarantined count is tracked in `COUNT`.

# Training data

Supply consented, labelled RGB images in this exact structure:

```text
dataset/raw/
  negative/
  positive/
  inconclusive/
```

Use `jpg`, `jpeg`, `png`, or `webp` images. The trainer rejects a run until each
class contains at least five readable images; practical evaluation needs a much
larger, balanced and independently held-out dataset.

Do not commit sensitive case imagery, identifiers, or location data. Keep real
evidence in approved storage with dataset provenance, label-review records and
consent documentation. A validation accuracy alone is not release approval.

# Locked demo-paper portfolio

The demo uses a narrow, declared subset of each paper, not a misleading claim of reproducing every
benchmark row. Exact claims are accepted only after the reader extracts them from the downloaded PDF.

## Primary — ROCKET

- Paper: [ROCKET: Exceptionally fast and accurate time series classification using random convolutional kernels](https://arxiv.org/abs/1910.13051)
- Official implementation: [angus924/rocket](https://github.com/angus924/rocket)
- Data: public UCR time-series archive; start with GunPoint and ItalyPowerDemand.
- Why it fits: CPU-oriented method, clear accuracy/runtime claims, official code, figures and tables.
- Demo scope: one accuracy claim and one runtime/ordering claim on a fixed public dataset and seed.

## Primary — MiniRocket

- Paper: [MINIROCKET: A Very Fast (Almost) Deterministic Transform for Time Series Classification](https://arxiv.org/abs/2012.08791)
- Official implementation: [angus924/minirocket](https://github.com/angus924/minirocket)
- Data: public UCR time-series archive; use the same dataset pair for cross-paper memory reuse.
- Why it fits: almost deterministic, CPU-fast, strong runtime story, direct comparison against ROCKET.
- Demo scope: accuracy delta and transform runtime on a fixed dataset/seed; display the paired figure.

## Deliberately hard background run — XGBoost

- Paper: [XGBoost: A Scalable Tree Boosting System](https://arxiv.org/abs/1603.02754)
- Official implementation: [dmlc/xgboost](https://github.com/dmlc/xgboost)
- Why keep it: recognizable system, richer dependency/build surface, useful long-running async example.
- Constraint: headline benchmark scale exceeds the demo budget. Replicator must mark those claims
  `NOT_ATTEMPTED` rather than silently downscale them; only explicitly scoped public subsets may run.

## Lock gate before recording

For each primary paper, preserve the source PDF hash, dataset checksum, generated source hash, container
digest, metrics artifact, figure pair, total cost, and trace URL. If either run exceeds 20 minutes or
requires manual repair, replace it before recording rather than editing around the failure.

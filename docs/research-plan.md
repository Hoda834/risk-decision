# Research evaluation plan, not results

The four supplied JOSS papers concern different computational tasks. RiskPortfolios
(10.21105/joss.00171) implements portfolio methods and covariance estimators and cites a
simulation study. CoPro (10.21105/joss.02855) provides configurable conflict prediction
workflows, including SVC, KNN and random forests. PyMSM (10.21105/joss.04566) implements
multi-state survival models, competing risks and Monte Carlo paths with real-data examples.
qPOTS (10.21105/joss.10867) implements constrained multiobjective Bayesian optimisation
and describes methodological benchmarks and research applications. Their subject matter
does not establish that an operational risk register is equivalent research software.

For Risk Decision, first establish whether supported text extraction helps reviewers
complete an assessment without increasing unsupported statements. Compare manual and
assisted entry using the same versioned policy, matched case difficulty, counterbalanced
assignment and no repeat exposure to the same case by the same reviewer. Prepare source
texts and independently annotated event/cause/consequence spans. Resolve annotation
disagreements explicitly. Preserve a held-out set before prompt changes.

Record model/version, prompt version, source hash, duration, original suggestions, edits,
missing fields, unsupported statements and the final decision. Measure field-level
precision and recall, unsupported-claim rate, review time and correction burden. Report
null results and uncertainty; synthetic examples are engineering checks, not adoption.
Actual organisational risk outcomes require a separate longitudinal study with defined
observation windows, exposure counts and censoring. Do not infer prevented incidents
merely because none was observed.

Version 0.4 is the pilot implementation. Its research contribution and usefulness outside
the originating team remain to be demonstrated. The intake provider is replaceable;
adding a model does not itself establish scholarly significance.

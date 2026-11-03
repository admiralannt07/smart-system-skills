# Source caveats and verified interpretations

Physical slide numbers and exact revisions are in sources.json. Original wording/equation structures are preserved in the linked native extraction and ingestion reports. Operational interpretations below do not modify those sources.

Independent grouped interpolation reference: [PolyU Descriptive Statistics, printed pages 21-23](https://www.polyu.edu.hk/ama/stat/pdf/lectnote/c1_des.pdf). Median interpolation assumes a distribution within the class; the usual mode interpolation requires a defensible modal class and comparable class widths. An unresolved plateau, edge class or unequal-width case needs an explicit model, rather than blind substitution.

| Source | Caveat and required handling |
| --- | --- |
| D1:7 | The sample formula uses population N. Use sample n with indexed observations; retain the discrepancy. |
| D1:23 | Primary/secondary data depends on collection purpose and research role. Logs are not inherently secondary. |
| D1:32-34 | Bar/line units are incomplete; the pie lacks visible category labels. Cached values do not establish visible labels. Attribute cache-derived reconstructions explicitly. |
| D1:35 | The depicted histogram has bar gaps; the last class is open-ended. Do not infer a finite width or density from the picture. |
| D1:36-37 | Boxplot whisker convention is unspecified; scatter chart has no native points. Do not invent observations or whisker rules. |
| D1:41 | Expanded mean uses superscripts inconsistent with indexed observations. Use indices, not powers. |
| D1:47,49 | Grouped median/mode need true lower boundary, class width, and frequencies. Standard interpolations are L+h(n/2-F_before)/f_median and L+h*d1/(d1+d2), with d1=f_modal-f_previous and d2=f_modal-f_next. Do not solve from ambiguous class boundaries. |
| D1:50 | Mean/median skew ordering is a heuristic, not a theorem for arbitrary data. |
| D1:60 | Sample variance is printed with mu and upper N. Center on x-bar and sum the n sample values with denominator n-1. |
| D1:63,69 | Quantile algorithm is unspecified. State the chosen algorithm before IQR/outlier results; flags are not automatic deletion decisions. |
| D1:67 | Formula is Pearson second skewness, not moment skewness. Zero SD makes it undefined. |
| D2:11 | At-least-one-UP set {UU,UD,DU} is an event, whereas full Omega is {UU,UD,DU,DD}. The slide overloads Omega. |
| D2:14 | Indexed omega labels events consistently locally. The OTP event is {AOW,AOS,IOW,IOS}; Android+Wifi event {APW,AOW}; intersection {AOW}. These are AI-derived exercise solutions. |
| D2:31 | n!/product(r_i!) counts full multiset arrangements with sum(r_i)=n. Do not apply it to partial distinct selection P(n,r). |
| D2:43 | Native Office Math and LibreOffice render agree on n!/(r!(n-r)!). Cached fallback differs. PowerPoint rendering parity remains unchecked. |

## Validation limits

Ingestion result 25782e1f326b3065 records 123 slides inspected, 110 reviewed with evidence, 13 partial, and 88 passing calculations. This is evidence coverage, not proof that all source assertions are correct. The packaged skills restrict ambiguous procedures explicitly. No learner mastery or complete formal syllabus is inferred.

For small reports (D1:71), state objective, data/source and observation unit, method/assumptions, numerical results with units, suitable chart when useful, interpretation, and limitations. This is cross-cutting guidance, not another routing level.

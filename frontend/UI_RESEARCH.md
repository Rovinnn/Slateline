# Dense information UI research

## Findings applied

1. Put frequent, decision-critical information in the initial view. Nielsen Norman Group describes progressive disclosure as a split between frequent primary features and specialized secondary features, and warns that going beyond two disclosure levels can make users lose their way. Slateline therefore shows the recommendation, net benefit, key comparison metrics, risks, funding status, shortlist, and split result immediately. [Progressive Disclosure — Nielsen Norman Group](https://www.nngroup.com/articles/progressive-disclosure/)

2. Do not use disclosure controls for information most users need. GOV.UK recommends its details component for one short, less-important section and explicitly advises against hiding information the majority of users need. The latest concept contains no accordions or HTML `details` elements. [Details — GOV.UK Design System](https://design-system.service.gov.uk/components/details/)

3. Use tabs where users need one section at a time and must switch quickly without moving the page. The four main product modes stay as tabs, and the focused location panel uses tabs for Summary, Calculation, Program, and Evidence. [Tabs — GOV.UK Design System](https://design-system.service.gov.uk/components/tabs/)

4. Use a table for repeated comparable data, and expose row-specific depth from the row. Carbon recommends data tables for organized resources and expandable rows for row-level progressive disclosure. Slateline uses a compact shortlist on the memo and a sortable comparison table; selecting a row opens the same focused detail panel rather than adding a vertical accordion. [Data table usage — Carbon Design System](https://carbondesignsystem.com/components/data-table/usage/)

5. Keep important differences explicit. Nielsen Norman Group recommends highlighting the few differences that matter most when options have many attributes. The overview emphasizes net benefit, effective return, qualified spend, relocation, gap to runner-up, and decision risk. [Explicitly State the Difference Between Options — Nielsen Norman Group](https://www.nngroup.com/articles/explicit-differences/)

6. Follow standard keyboard behavior. The detail panel uses the native modal dialog, closes with Escape, and has a visible close button. Its tab lists support Left/Right Arrow, Home, and End. [Modal Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) and [Tabs Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)

## Information hierarchy

- Level 1: recommendation, key numbers, risk/funding status, shortlist, split result.
- Level 2: a single focused panel for the selected location, pre-commit checks, or model controls.
- Alternate views: comparison table, map, and incentive gap remain in the existing primary tabs.

This concept needs usability testing with producers before production adoption. The research supports the interaction patterns; it does not determine which facts this specific audience consults most often.

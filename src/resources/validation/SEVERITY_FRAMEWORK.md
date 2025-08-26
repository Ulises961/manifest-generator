| **Category**           | **Type** | **Relevance**           | **Nuance**                                            | **Severity** |
| ---------------------- | -------- | ----------------------- | ----------------------------------------------------- | ------------ |
| Main property          | Missing  | Belongs to MWC category | Whole property missing                                | **Critical** |
| Main property          | Missing  | Belongs to MWC category | Partial parameter missing – breaks the property       | **Critical** |
| Main property          | Missing  | Belongs to MWC category | Partial parameter missing – does not affect behaviour | **Medium**   |
| Main property          | Missing  | Does NOT belong to MWC  | Any nuance                                            | **High**      |
| Main property          | Extra    | Belongs to MWC category | Any nuance                                            | **Medium**   |
| Main property          | Extra    | Does NOT belong to MWC  | Any nuance                                            | **Low**      |
| Main property          | Modified | Belongs to MWC category | Any nuance                                            | **Low**      |
| Main property          | Modified | Does NOT belong to MWC  | Any nuance                                            | **Low**      |
| Property parameter     | Missing  | —                       | Breaks property                                       | **Critical** |
| Property parameter     | Missing  | —                       | Does not affect behaviour                             | **Medium**   |
| Property parameter     | Extra    | —                       | Redundant but benign                                  | **Medium**   |
| Property parameter     | Modified | —                       | Slightly altered semantics                            | **Low**      |
|— | Manually Reviewed | Modified | Is present but not identified automatically | **Info** 
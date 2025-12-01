| **Category**           | **Type** | **Relevance**           |  **Severity** |
| ---------------------- | -------- | ----------------------- |  ------------ |
| Main property          | Missing, Extra, Different | Breaks deployment, impedes correct behaviour |  **Critical** |
| Main property          | Missing, Extra, Different | Application runs but has a severe security flaw  | **High** |
| Main property          | Missing, Extra, Different | Impacts on pods preemption, scheduling, affinity. | **Medium** |
| Main property          | Missing, Extra, Different | Low impact on application e.g.labels, number of replicas | **Low** |
| Property parameter     | Missing  | Breaks main property | **Critical** |
| Property parameter     | Missing  | Advisable to be present but not essential | **Medium**   |
| Property parameter     | Extra    | Advisable to be present but not essential | **Low**   |
| Property parameter     | Modified | —                       | **Low**      |
|— | Manually Reviewed | Is present but not identified automatically | **Info** 
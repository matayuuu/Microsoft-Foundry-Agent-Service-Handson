# Screenshot attribution

The following Microsoft product UI screenshots are reproduced from Microsoft Learn under the
[Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/).
Microsoft and Azure product names and logos remain trademarks of Microsoft. Their use here does not
imply endorsement.

| Workshop image | Microsoft Learn source | Modification |
|---|---|---|
| `lab01-azureml-compute.png` | [Create an Azure Machine Learning compute instance](https://learn.microsoft.com/azure/machine-learning/how-to-create-compute-instance) | None |
| `lab01-azureml-idle-shutdown.png` | [Create an Azure Machine Learning compute instance](https://learn.microsoft.com/azure/machine-learning/how-to-create-compute-instance#configure-idle-shutdown) | Cropped to the idle-shutdown control; the sample duration was excluded because this workshop uses 30 minutes |
| `lab01-azureml-upload.png` | [Customize a compute instance](https://learn.microsoft.com/azure/machine-learning/how-to-customize-compute-instance) | None |
| `lab09-delete-resource-group.png` | [Microsoft Learn shared resource-group cleanup instructions](https://github.com/MicrosoftDocs/azure-docs/blob/main/includes/alt-delete-resource-group.md) | None |

The source repositories are
[`MicrosoftDocs/azure-docs`](https://github.com/MicrosoftDocs/azure-docs) and
[`MicrosoftDocs/azure-ai-docs`](https://github.com/MicrosoftDocs/azure-ai-docs).

The Azure ML images apply to Lab 7 environment preparation despite their historical `lab01-`
filenames. The resource-group deletion image is a general Microsoft Learn example, not evidence
of this workshop's cleanup. `workshop-architecture.svg` and `workshop-learning-flow.svg` are
original explanatory diagrams with editable `.excalidraw` sources, not product UI captures.

## Workshop Portal captures

These screenshots were captured with Playwright during the actual successful custom-template
deployment and authenticated private-Blob download. They are not generated UI or simulated
results. Account banners and individual resource identifiers were cropped or masked; blue
outlines highlight the relevant controls. Microsoft product names and UI remain Microsoft's.

| Workshop image | Actual screen | Modification |
|---|---|---|
| `lab01-template-succeeded.png` | Azure Portal deployment Overview: Your deployment is complete | Cropped; deployment, subscription, RG, timestamp and correlation values masked; completion highlighted |
| `lab01-bootstrap-outputs.png` | Deployment Script Outputs: complete and private ZIP coordinates | Cropped; storage-account name masked; status highlighted |
| `lab01-private-zip-download.png` | Storage browser: Microsoft Entra user account and Download | Account/resource header cropped out; authentication method and Download highlighted |

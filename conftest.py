16:26:29  [Pipeline] sh
16:26:30  + aws ecr describe-repositories --region eu-west-2
16:26:31  {
16:26:31      "repositories": [
16:26:31          {
16:26:31              "repositoryArn": "arn:aws:ecr:eu-west-2:975359590581:repository/sb-pdev-d37f6745-5680-4868-91f2-a03906a8b21c-ecr-repo",
16:26:31              "registryId": "975359590581",
16:26:31              "repositoryName": "sb-pdev-d37f6745-5680-4868-91f2-a03906a8b21c-ecr-repo",
16:26:31              "repositoryUri": "975359590581.dkr.ecr.eu-west-2.amazonaws.com/sb-pdev-d37f6745-5680-4868-91f2-a03906a8b21c-ecr-repo",
16:26:31              "createdAt": "2026-04-21T11:12:52.462000+00:00",
16:26:31              "imageTagMutability": "MUTABLE",
16:26:31              "imageScanningConfiguration": {
16:26:31                  "scanOnPush": true
16:26:31              },
16:26:31              "encryptionConfiguration": {
16:26:31                  "encryptionType": "AES256"
16:26:31              }
16:26:31          }
16:26:31      ]
16:26:31  }


So looks like this ECR repo is already present in the ABSA account. I guess we can just reuse the saem

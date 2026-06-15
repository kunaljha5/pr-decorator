# PR Decorator

Automatically analyses and decorates pull requests using **Amazon Bedrock Nova Pro**. Triggered on every PR open, update, or reopen- no manual input needed.

---

## What it does

When a PR is opened or updated, the workflow:

1. Authenticates with AWS using OIDC (no stored access keys)
2. Calls Amazon Bedrock Nova Pro to analyse the PR diff
3. Updates the PR body with a structured summary
4. Posts a completion comment


## Sequence Diagram

[![](https://mermaid.ink/img/pako:eNqFVt1u4kYUfpWRL6qsCsYGDMSqIjmgbmiVDQLaSBVSNbYHGMWecWfGZNko0r5AL_qjXlXam170Hfo2eYJ9hJ4zBkOXbGoh8M93fr_vHPPgJDJlTuho9lPJRMJGnK4UzReCwEFLI0WZx0wtxO5OYqQiI7YhVJOPH375--n9zx8__PoP3mKZLBCJuIIqwxNeUGHIlBUS4a-5uSpje3kKmkwRMimzDACQijanmNdX0ZGfKDFcCv0M7GY8Gh4B7eVEyQ1PmfoqVq2LMyPvmHBp5cFdcbMu41IzlUhhmDBuIvNXp45n8xm6jW5neFp50ka7NKfvpKD3-jN24-ga7fBnKjNGviQTmfFke4qM9qljjJuCifHIhhlKIRi2_tTk0jYusimQS5YqmdxZmzdyQ7FschZNouGrPYMK_BC1is_aHa9B2l38CoJd1ni8kYYRuWGW5sZkGpKn39_Dh8wVX63gdnV5MABY8-ICaQ2BQL0msaIiWZMWAT0IYPYARRBg0elQMQqBThnHYzIFFNAd1kHvpbpbZvK-6roUISnA8kdVWe7SZyI9LTMIsMwBfHW8Z8uEOA3b-LpSy0JUmjVogScUVXJSNVhhjpWdT919EeSb2zmx-jrCIqq5L8mPEWxKJYjmK8FSNFmIT12DxELSdkmkdZkzFM4t6PSWxeMU0zLbMzA7KgjwYLUrpOuS72nGU2wxJkRXlAttbPcUW3FtmILAttBiNxoHV9E-X5sD2m_QGXn687dP44GoQ9I5RNPEqBK6UFiF23hfEGoMTdYQD_ZDzrU-zC0e4KKOVQ0GoRlQrUlcyTkciw009Bo2VXaaw76tQd1Vw_KCJFAf9olmutJMlCRM62_ZdpzCBM6YTWOORDWIH5Cci5dU1KnmxE7MZ1V0eRiW3SQSTP1FBaFNz92X2lQl5Jwzwm3JzRxrtvnbs5BUu8YVMNxNIK658UPPPo9lug1xjaZ8uYQC7Sp7WzEOe3wdnrTluSowGy6WIA54F6Ayljxjra9lKdKqiOs6ISVLpDtRUusmagqeGmkfyQJqoBmpVxC0tJBcHE345bQmru_a7S9ottVcQ891Afpg-_2qygRYBfHAGORUbf-XpZdWGrJ0tNIg7oglUr1EEMIHMN-TaD68Ii1cO7r1UL0WH22S3xV2zsAZkkDuYUzrcp71BgtgcjObkxbMAuyM2lsL3h85sFMpNkpTYDEvMmaz2z37z5IEh7B9Q3gT__WH5b4qBpplk4jG-6Yd9cxpOCvFUyeEzrKGk8NIUrx0HhC0cGDr5WzhhHCasiUtM7NwFuIRzOB984OU-d4SBLBaO-ESpARXpW3C7u9DfRd0BJtlCPoxTtjtWx9O-OC8dcJm-9xzvUF74He8oNPtB1634WzhfqfbczuDcz_wznuD_mDQe2w472xc3w26fr_vD7rBeafneW3_8V-NudP3?type=png)](https://mermaid.live/edit#pako:eNqFVt1u4kYUfpWRL6qsCsYOcQJWFckh6oZW2SCgjVQhVWN7MKPYM-7MmCwbRdoX6EV_1KtKe9OLvkPfJk-wj9BzxtjQJZtaCPzznd_vO8c8OIlMmRM6mv1UMZGwS04zRYuFIHDQykhRFTFTC7G9kxipyCVbE6rJxw-__P30_uePH379B2-xXJaIRFxJleEJL6kwZMpKifDX3FxVsb08BE2mCJlUeQ4ASEWbQ8zrq2jPT5QYLoV-BnYzvhztAe3lRMk1T5n6Kla98yMj75hwae3BzbhZVXGlmUqkMEwYN5HFq0PHs_kM3Ua3MzytPWmjXVrQd1LQe_0Zu3F0jXb4M5U5I1-Sicx5sjlERk3qGOOmZGJ8acOMpBAMW39ocmEbF9kUyAVLlUzurM0buaZYNjmKJtHoVcOgAj9EZfHRcd_rkOMT_AqCbdZ4vJGGEblmlubOZBqSp9_fw4fMFc8yuF1f7gwA1j0_R1pDIFCvSKyoSFakR0APApjdQREEWHQ6UoxCoEPG8ZhMAQV0h23Qe6nulrm8r7suRUhKsPxR1Zbb9JlID8sMAixzAF9979kyIU7HNr6t1LIQVWYFWuAJRZUcVA1WmGNt51O3KYJ8czsnVl97WER1m5L8GMGmUoJongmWoslCfOoaJBaSY5dEWlcFQ-Hcgk5vWTxOMS2zOQKzvYIAD1bbQk5c8j3NeYotxoRoRrnQxnZPsYxrwxQEtoWW29HYuYqafG0OaL9GZ-Tpz98-jQeiDkl_F00ToyroQmkVbuN9QagxNFlBPNgPBdd6N7d4gIs2Vj0YhOZAtSZxLedwLNbQ0GvYVPlhDk1bg7arhhUlSaA-7BPNda2ZKEmY1t-yzTiFCZwxm8YcieoQPyAFFy-pqF_PiZ2Yz6roYjcs20kkmPqLCkKbU7cptasqyLlghNuSuwXWbPO3ZyGpd40rYLi7QFx37YeefR7LdBPiGk35cgkF2lX2tmYc9vgqPGjLc1VgNlwsQRzwLkBlLHnOel_LSqR1EddtQkpWSHeipNZd1BQ8NdI-kiXUQHPSriBoaSm52Jvwi2lL3Jlrt7-g-UZzDT3XJeiDNftVVQmwCuKBMSio2vwvSy-tNGRpb6VB3EuWSPUSQQgfwHxPovnoivRw7ejeQ_1afLRJflfaOQNnSAK5hzFty3nWGyyAyc1sTnowC7AzWm89eH8UwE6t2ChNgcWizJnNbvvsP0sSHML2DeFN_Ncflvu6GGiWTSIaN03b65nTcTLFUyeEzrKOU8BIUrx0HhC0cGDrFWzhhHCasiWtcrNwFuIRzOB984OURWMJAshWTrgEKcFVZZuw_fvQ3gUdwWYZgX6MEw6tCyd8cN46Yfd40HeDgT_w_UHQD049_6zjbOB-_8R3g77neafDoXcyBCYfO847G9c-GAwGQz_wTv1h4J09_guN69Py)

```mermaid
sequenceDiagram
    autonumber

    actor Dev as 👨‍💻 Developer
    participant Repo as GitHub Repo
    participant PR as Pull Request
    participant GHA as GitHub Actions
    participant GOIDC as GitHub OIDC Provider<br/>(token.actions.githubusercontent.com)
    participant STS as AWS STS<br/>(sts.amazonaws.com)
    participant IAM as IAM Role + Policy
    participant AOIDC as AWS OpenID<br/>Connector
    participant BR as Amazon Bedrock<br/>Nova Pro (APAC)

    rect rgb(230, 240, 255)
        Note over Dev,PR: ── Trigger ──
        Dev->>Repo: Push branch / open PR
        Repo->>PR: Create Pull Request
        PR->>GHA: Trigger workflow<br/>(on: pull_request)
    end

    rect rgb(255, 248, 230)
        Note over GHA,AOIDC: ── OIDC Authentication ──
        GHA->>GOIDC: 1a. Request JWT token
        GOIDC-->>GHA: 1b. Return signed JWT

        GHA->>STS: 2. AssumeRoleWithWebIdentity(JWT)
        STS->>AOIDC: 4. Validate JWT against<br/>registered OIDC provider
        AOIDC-->>STS: JWT valid ✓
        STS->>IAM: 3. Validates trust policy<br/>& attached permissions
        IAM-->>STS: Policy allows bedrock:InvokeModel ✓
        STS-->>GHA: 5. Return temp credentials<br/>(AccessKeyId + SessionToken, 15 min)
    end

    rect rgb(230, 255, 240)
        Note over GHA,BR: ── Bedrock Invocation ──
        GHA->>BR: 6. bedrock-runtime invoke-model<br/>model: amazon.nova-pro-v1:0<br/>body: PR diff + context<br/>auth: temp credentials
        Note over BR: inference profile/Foundation Model<br/>routes cross-region to<br/>optimal Nova Pro endpoint
        BR-->>GHA: 7. PR analysis response<br/>(structured summary)
    end

    rect rgb(230, 240, 255)
        Note over GHA,PR: ── PR Decoration ──
        GHA->>PR: 8a. PATCH /pulls/{number}<br/>Update PR body with analysis
        GHA->>PR: 8b. POST /issues/{number}/comments<br/>Add completion comment
        PR-->>Dev: 🤖 PR decorated with AI summary
    end
```

---

## Architecture

![pr-decorator.drawio.png](https://raw.githubusercontent.com/kunaljha5/pr-decorator/refs/heads/main/images/pr-decorator.drawio.png)

## How authentication works

This setup uses **OpenID Connect (OIDC)**. GitHub generates a short-lived token per workflow run. AWS trusts that token and returns temporary credentials- no `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` stored anywhere.

---

## Prerequisites

- AWS account with Bedrock access enabled for **Amazon Nova Pro**
- Admin access to your GitHub repository
- AWS CLI installed locally (for setup commands)

---

## Step 1: AWS setup

### 1a. Register GitHub as an identity provider

Run this once per AWS account:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```

> **Note:** If you get `EntityAlreadyExists`, the provider is already registered — skip this step.

---

### 1b. Create the IAM trust policy

Create `trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<YOUR_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:{YOUR_GITHUB_USERNAME||YOUR_GITHUB_ORG}/YOUR_REPO_NAME:*"
      }
    }
  }]
}
```

Replace:

| Placeholder            | Replace with                           |
|------------------------|----------------------------------------|
| `YOUR_ACCOUNT_ID`      | Your 12-digit AWS account ID           |
| `YOUR_GITHUB_USERNAME` | Your GitHub username name              |
| `YOUR_GITHUB_ORG`      | Your GitHub org name                   |
| `YOUR_REPO_NAME`       | Exact repository name (case-sensitive) |


---

### 1c. Create the IAM role

```bash
aws iam create-role \
  --role-name pr-decorator-bedrock-role \
  --assume-role-policy-document file://trust-policy.json \
  --description "Role for GitHub Actions PR Decorator"
```

---

### 1d. Create and attach the Bedrock access policy

Create `bedrock-policy.json`:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowNovaModelsApSouth1Only",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:::foundation-model/amazon.nova-lite-v1:0",
                "arn:aws:bedrock:::foundation-model/amazon.nova-pro-v1:0",
                "arn:aws:bedrock::<YOUR_ACCOUNT_ID>:inference-profile/apac.amazon.nova-pro-v1:0",
                "arn:aws:bedrock::<YOUR_ACCOUNT_ID>:inference-profile/apac.amazon.nova-lite-v1:0"
            ]
        }
    ]
}
```

Attach it:

```bash
aws iam create-policy \
  --policy-name BedrockProfilePolicy \
  --policy-document file://bedrock-policy.json

aws iam attach-role-policy \
  --role-name pr-decorator-bedrock-role \
  --policy-arn arn:aws:iam::<YOUR_ACCOUNT_ID>:policy/BedrockProfilePolicy
```

---

### 1e. Enable Nova Pro model access

1. Go to the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock)
2. Click **Model access** in the left navigation
3. Find **Amazon Nova Pro** and click **Request access**
4. Wait for approval (usually instant)

---

## Step 2: GitHub setup

### 2a. Add repository secret

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name        | Value                                                           |
|--------------------|-----------------------------------------------------------------|
| `AWS_IAM_ROLE_ARN` | `arn:aws:iam::<YOUR_ACCOUNT_ID>:role/pr-decorator-bedrock-role` |

### 2b. Add repository variables

On the same page, click the **Variables** tab:

i.e apac preferred region set 

| Variable name          | Value                       |
|------------------------|-----------------------------|
| `AWS_REGION`           | `ap-south-1`                |
| `AWS_BEDROCK_MODEL_ID` | `apac.amazon.nova-pro-v1:0` |

### 2c. Add the workflow file

Create `.github/workflows/pr-decorator.yml`:

```yaml
name: PR Decorator (Automatic)

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches:
      - main

permissions:
  contents: read
  pull-requests: write
  id-token: write   # required for OIDC

jobs:
  decorate-pr:
    runs-on: ubuntu-latest
    # Block fork PRs — they cannot access secrets
    if: github.event.pull_request.head.repo.full_name == github.repository

    steps:
      - name: Checkout code
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v6
        with:
          role-to-assume: ${{ secrets.AWS_IAM_ROLE_ARN }}
          role-session-name: GitHubActions-AutoPRDecorator
          aws-region: ${{ vars.AWS_REGION }}

      # ubuntu-latest ships with CLI v1 which lacks bedrock-runtime
      - name: Upgrade AWS CLI
        run: |
          curl -s https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
          unzip -q awscliv2.zip
          sudo ./aws/install --update

      - name: Test Bedrock access
        run: |
          aws bedrock-runtime invoke-model \
            --model-id ${{ vars.AWS_BEDROCK_MODEL_ID }} \
            --body '{"messages":[{"role":"user","content":[{"text":"ping"}]}]}' \
            --region ${{ vars.AWS_REGION }} \
            --cli-binary-format raw-in-base64-out \
            test-response.json
          echo "Bedrock access confirmed"

      - name: Run PR decorator
        uses: ./
        with:
          pr-decorator-version: source
          pr-number: ${{ github.event.pull_request.number }}
          base-sha: ${{ github.event.pull_request.base.sha }}
          head-sha: ${{ github.event.pull_request.head.sha }}
          head-ref: ${{ github.event.pull_request.head.ref }}
          aws-region: ${{ vars.AWS_REGION }}
          region: ${{ vars.AWS_REGION }}
          mode: "body"
          overwrite: "false"

      - name: Add completion comment (optional)
        uses: actions/github-script@v9
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: ${{ github.event.pull_request.number }},
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '🤖 **PR Decorator Complete**\n\nAnalysed using AWS Bedrock Nova Pro (APAC).\n\n_Triggered by: ${{ github.event_name }} on ${{ github.event.pull_request.head.ref }}_'
            })
```

---

## Step 3: Verify

Create a test PR to trigger the workflow:

```bash
git checkout -b test/bedrock-setup
echo "test" >> README.md
git add README.md
git commit -m "test: trigger PR decorator"
git push origin test/bedrock-setup
```

Open a PR targeting `main`. In the **Actions** tab, a successful run shows all steps green, the PR body updated, and a completion comment posted.

---

## Troubleshooting

| Error                                                     | Cause                                                           | Fix                                                                                                                |
|-----------------------------------------------------------|-----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | Trust policy `sub` condition mismatch, or OIDC provider missing | Verify provider exists: `aws iam list-open-id-connect-providers`. Check repo name in trust policy matches exactly. |
| `Found invalid choice 'invoke-model' under bedrock`       | Wrong CLI namespace                                             | Use `aws bedrock-runtime invoke-model`, not `aws bedrock invoke-model`                                             |
| `AccessDenied` on `bedrock:InvokeModel`                   | Policy not attached, or wrong resource ARN                      | Run `aws iam list-attached-role-policies --role-name pr-decorator-bedrock-role`                                    |
| Model access denied                                       | Nova Pro not enabled                                            | Go to Bedrock console → Model access → enable Amazon Nova Pro                                                      |

### Verify your setup

```bash
# Check OIDC provider exists
aws iam list-open-id-connect-providers

# Check trust policy
aws iam get-role \
  --role-name pr-decorator-bedrock-role \
  --query Role.AssumeRolePolicyDocument

# Check attached policies
aws iam list-attached-role-policies \
  --role-name pr-decorator-bedrock-role

# Test Bedrock directly
aws bedrock-runtime invoke-model \
  --model-id apac.amazon.nova-pro-v1:0 \
  --body '{"messages":[{"role":"user","content":[{"text":"hello"}]}]}' \
  --region ap-south-1 \
  --cli-binary-format raw-in-base64-out \
  response.json && cat response.json
```

---

## Security notes

- Fork PRs are blocked — the `if:` condition prevents forks from accessing secrets
- OIDC tokens are short-lived (15 min) and scoped to a single workflow run
- The IAM role is limited to `bedrock:InvokeModel` only- no broader AWS access
- The trust policy `sub` condition locks the role to this specific repository
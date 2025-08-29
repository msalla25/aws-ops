87provider "aws" {
  region = "us-west-2"  # Replace with your desired region
}

resource "aws_sfn_state_machine" "ecs_restart_state_machine" {
  name     = "ecs-restart-state-machine"
  role_arn = aws_iam_role.step_functions_role.arn
  definition = file("path-to-your-state-machine.json")  # Place the JSON above in a separate file
}

resource "aws_cloudwatch_event_rule" "high_cpu_alarm_rule" {
  name        = "high-cpu-alarm-rule"
  description = "CloudWatch rule to trigger Step Functions on high CPU utilization"
  event_pattern = <<EVENT_PATTERN
{
  "source": ["aws.ecs"],
  "detail-type": ["ECS Task State Change"],
  "detail": {
    "clusterArn": ["arn:aws:ecs:region:account-id:cluster/your-cluster-name"],
    "group": ["service:your-service-name"]
  }
}
EVENT_PATTERN
}

resource "aws_lambda_function" "cloudwatch_trigger_lambda" {
  filename         = "lambda.zip"  # Replace with your zipped Lambda code
  function_name    = "cloudwatch-trigger-lambda"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = filebase64sha256("lambda.zip")
  
  environment {
    variables = {
      STEP_FUNCTION_ARN = aws_sfn_state_machine.ecs_restart_state_machine.arn
    }
  }
}

resource "aws_lambda_function" "api_gateway_trigger_lambda" {
  filename         = "lambda.zip"  # Replace with your zipped Lambda code
  function_name    = "api-gateway-trigger-lambda"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = filebase64sha256("lambda.zip")
  
  environment {
    variables = {
      STEP_FUNCTION_ARN = aws_sfn_state_machine.ecs_restart_state_machine.arn
    }
  }
}

resource "aws_cloudwatch_event_target" "target" {
  rule      = aws_cloudwatch_event_rule.high_cpu_alarm_rule.name
  target_id = "LambdaTarget"
  arn       = aws_lambda_function.cloudwatch_trigger_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_invoke" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cloudwatch_trigger_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.high_cpu_alarm_rule.arn
}

resource "aws_api_gateway_rest_api" "ecs_restart_api" {
  name        = "ecs-restart-api"
  description = "API to trigger ECS restart via Step Functions"
}

resource "aws_api_gateway_resource" "ecs_restart_resource" {
  rest_api_id = aws_api_gateway_rest_api.ecs_restart_api.id
  parent_id   = aws_api_gateway_rest_api.ecs_restart_api.root_resource_id
  path_part   = "restart-service"
}

resource "aws_api_gateway_method" "post_method" {
  rest_api_id   = aws_api_gateway_rest_api.ecs_restart_api.id
  resource_id   = aws_api_gateway_resource.ecs_restart_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.ecs_restart_api.id
  resource_id             = aws_api_gateway_resource.ecs_restart_resource.id
  http_method             = aws_api_gateway_method.post_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api_gateway_trigger_lambda.invoke_arn
}

resource "aws_api_gateway_deployment" "ecs_restart_api_deployment" {
  depends_on = [aws_api_gateway_method.post_method]
  rest_api_id = aws_api_gateway_rest_api.ecs_restart_api.id
  stage_name  = "prod"
}

resource "aws_lambda_permission" "allow_api_gateway_invoke" {
  statement_id  = "AllowExecutionFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_gateway_trigger_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.ecs_restart_api.execution_arn}/*/*"
}

resource "aws_iam_role" "step_functions_role" {
  name = "ecs-restart-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "step_functions_policy" {
  name        = "ecs-restart-step-functions-policy"
  description = "Policy to allow Step Functions to manage ECS services"
  policy      = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action   = [
          "ecs:StopTask",
          "ecs:DescribeTasks"
        ],
        Effect   = "Allow",
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "step_functions_policy_attachment" {
  role       = aws_iam_role.step_functions_role.name


index=<your_index> source=<your_log_source>
| rex field=_raw "(?<response_time>\d+)msec"
| eval response_time = tonumber(response_time)
| eventstats perc90(response_time) as p90_response_time
| table _time response_time p90_response_time


(100)*(custom:apigee.request.success.count:splitBy("proxy.name","request.path"):sum / (custom:apigee.request.count:splitBy("proxy.name","request.path"):sum):names
import os
import winrm

host = os.environ["WINRM_HOST"]
user = os.environ["WINRM_USER"]
wheel_path = os.environ["WHEEL_PATH"]

# establish kerberos-authenticated winrm session over https/5986
session = winrm.Session(
    f"https://{host}:5986/wsman",
    auth=(user, None),   # password not needed if Kerberos ticket from kinit exists
    transport="kerberos",
    server_cert_validation="ignore"
)

# 1. Ensure deploy folder
session.run_cmd("powershell", ["-Command", "New-Item -Path C:\\deploy -ItemType Directory -Force"])

# 2. Copy wheel file to VM (simple base64 transfer)
with open(wheel_path, "rb") as f:
    b64 = f.read().hex()
session.run_cmd("powershell", ["-Command", f"[IO.File]::WriteAllBytes('C:\\deploy\\{os.path.basename(wheel_path)}', [Convert]::FromHexString('{b64}'))"])

# 3. Create venv if missing
session.run_cmd("powershell", ["-Command", "if (!(Test-Path C:\\deploy\\venv)) { python -m venv C:\\deploy\\venv }"])

# 4. Install wheel into venv
session.run_cmd("powershell", [
    "-Command",
    "& { C:\\deploy\\venv\\Scripts\\Activate.ps1; pip install --upgrade pip; pip install C:\\deploy\\" + os.path.basename(wheel_path) + " }"
])

print("✅ Deployment completed successfully.")
import os
import winrm

host = os.environ["WINRM_HOST"]
user = os.environ["WINRM_USER"]
wheel_name = os.environ["WHEEL_NAME"]   # e.g. your_package-1.0.0-py3-none-any.whl
deploy_path = "C:\\deploy"
venv_path = os.path.join(deploy_path, "venv")

# Kerberos auth over HTTPS 5986
session = winrm.Session(
    f"https://{host}:5986/wsman",
    auth=(user, None),  # password not needed if kinit ticket exists
    transport="kerberos",
    server_cert_validation="ignore"
)

# Powershell script: find python, create venv if needed, install wheel
ps_script = f"""
$ErrorActionPreference = 'Stop'

# 1. Find python
$pyPaths = @(
    "C:\\Python311\\python.exe",
    "C:\\Program Files\\Python311\\python.exe",
    "C:\\Program Files (x86)\\Python311\\python.exe",
    "$env:LOCALAPPDATA\\Programs\\Python\\Python311\\python.exe"
)
$python = $pyPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $python) {{
    Write-Error "Python not found on VM."
    exit 1
}}

# 2. Ensure deploy folder
if (-not (Test-Path "{deploy_path}")) {{
    New-Item -Path "{deploy_path}" -ItemType Directory -Force | Out-Null
}}

# 3. Create venv if missing or incomplete
$venvScripts = Join-Path "{venv_path}" "Scripts\\python.exe"
if (-not (Test-Path $venvScripts)) {{
    & $python -m venv "{venv_path}"
}}

# 4. Activate venv and install wheel
$activate = Join-Path "{venv_path}" "Scripts\\Activate.ps1"
& $activate
pip install --upgrade pip
pip install "{os.path.join(deploy_path, wheel_name)}"
"""

# Run the PowerShell script
res = session.run_ps(ps_script)

print("STDOUT:", res.std_out.decode())
print("STDERR:", res.std_err.decode())

if res.status_code != 0:
    raise Exception(f"Deployment failed with exit code {res.status_code}")
else:
    print("✅ Deployment completed successfully.")

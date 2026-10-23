# Access denied

## Symptoms
AWS reports `AccessDenied` or `UnauthorizedOperation` during plan or apply.

## Verification
Identify the denied action and resource in sanitized pipeline logs. Confirm the deployment role and its policy with an operator. Check whether the role is using the intended AWS account.

## Next steps
Request a reviewed IAM change if the action is required by the approved template. Never grant broad permissions automatically from a diagnostic result.

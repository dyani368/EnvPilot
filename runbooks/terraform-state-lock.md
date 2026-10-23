# Terraform state lock

## Symptoms
Terraform reports an error acquiring its state lock.

## Verification
Find the existing build and determine whether it is still running. Inspect the S3 lockfile and state key associated with the same environment.

## Next steps
Wait for an active build to finish. Only an authorized operator may remove a stale lock after confirming no state operation is active.

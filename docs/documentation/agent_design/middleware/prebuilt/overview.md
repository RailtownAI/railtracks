# Prebuilt Middleware

We provide a suite of prebuilt middleware to help accelerate your agent builds. We have provied samples to get you started; for building your own, see [Custom Middleware](../custom.md).

## Model Middleware
Model middleware wraps the model call itself. Useful for acting on the inputs or outputs of the model, or for retry logic specific to the model call. Prebuilt model middleware includes:

!!! Note 
    [Guardrails](../../../advanced/guardrails/overview.md) are model middleware under the hood and can be attached just as any other middleware.

Check out our prebuilt tooling:

TABLE TBD

!!! Note
    Don't see what you are looking for... [Create your own middleware](../custom.md) to build a custom solution for your needs.



## Node Middleware
Node middleware wraps the entire node call. This is useful for logging, retries, caching, and similar concerns that are not specific to the model call itself.

Check out our prebuilt tooling:

TABLE TBD

!!! Note
    Don't see what you are looking for... [Create your own middleware](../custom.md) to build a custom solution for your needs.

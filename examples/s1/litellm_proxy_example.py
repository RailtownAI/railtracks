"""Triage support tickets with Jev through a LiteLLM proxy.

A LiteLLM proxy (https://docs.litellm.ai/docs/pass_through/typesafe) forwards
`/v1/systemone` calls to TypeSafe, Laya or Bespoke Nimble. The client holds only a
LiteLLM virtual key; the proxy adds the upstream's own key and tracks spend per key.
`rt.classifiers.LiteLLMProxyClassifier` sends to `{api_base}/{upstream}/v1/systemone`.

Needs a running proxy and a virtual key with access to the model (`typesafe/jev-latest`
here), set the way LiteLLM's own client reads them:

    export LITELLM_PROXY_API_BASE="http://localhost:4000"
    export LITELLM_PROXY_API_KEY="sk-..."   # a LiteLLM virtual key

The proxy itself needs TYPESAFE_API_KEY. For a Laya or Nimble upstream, set
`upstream="laya"` or `"bespoke"` and use that server's model name (e.g. "english");
those two routes need a proxy that includes LiteLLM PR #43626.

Run: uv run python examples/s1/litellm_proxy_example.py
"""

import railtracks as rt

TypeSafeSchema = rt.classifiers.TypeSafeSchema

jev_via_proxy = rt.classifiers.LiteLLMProxyClassifier(
    model_name="jev-latest",
    upstream="typesafe",
)


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team should handle this",
        criteria={
            "billing": "Charges, refunds, invoices, or plan changes",
            "technical": "Bugs, outages, errors, or integration problems",
            "sales": "Pricing questions, upgrades, or new purchases",
        },
    )


TriageTicket = rt.decision_node("Triage Ticket", model=jev_via_proxy, schema=Triage)
triage_flow = rt.Flow(name="Proxy Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke("I was charged twice for my March invoice.")

    print(result)  # is_urgent: no 0.21 | department: billing 0.96
    print(f"{result.model_name} via {result.provider}: cost ${result.cost}")

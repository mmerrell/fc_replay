"""The one place anything (mock API, poller, webhook receiver) turns a Cortex record into a Signal.

TODO: client.start_workflow(MemberWorkflow.run, ..., start_signal="ticket_purchased", start_signal_args=[...])
(signal-with-start creates the Member's workflow on its first event)."""

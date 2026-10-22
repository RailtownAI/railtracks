# Local Visualization (Legacy)

Use the current visualizer for new projects

This page covers the legacy (v1) visualizer, which reads the session files written by `save_state`. Those files are being replaced by the event stream, and so is this UI. For new projects, use the [current visualizer](https://docs.railtracks.org/observability/agenthub/local_v2/index.md) (`railtracks viz --beta`). The legacy visualizer is still the place to browse [evaluation results](https://docs.railtracks.org/evaluations/visualization/index.md) until the current visualizer supports them.

The legacy visualizer is in maintenance: it still gets security updates, but new features go into the current visualizer.

One of the number one complaints when working with LLMs is that they can be a black box. Agentic applications exacerbate this problem by adding even more complexity. Railtracks aims to make it easier than ever to visualize your runs.

We support:

- Local Visualization (**no sign up required**)
- Remote Visualization (Ideal for deployed agents)

## Local Development Visualization

The legacy visualizer runs locally with **no sign up required**.

Usage

Install CLI Tool

```bash
pip install 'railtracks[visual]'
```

Initialize UI and Start

```bash
railtracks init
railtracks viz
```

This will create a `.railtracks` directory at your project root and open the web app in your browser. Once initialised, railtracks will find that directory automatically, even if you run your agents from a subdirectory, by walking up the folder tree until it locates `.railtracks`.

Running from multiple directories?

Run `railtracks init` once from your project root (the same level as your `.git` folder). All subsequent agent runs across the project will resolve to that single `.railtracks` directory regardless of which subdirectory they are launched from.

If you need a fixed location outside your project (e.g. a shared drive or CI environment), set the `RAILTRACKS_HOME` environment variable to the **parent directory** where `.railtracks` should live:

```bash
export RAILTRACKS_HOME=/path/to/my/project   # .railtracks is created inside here
```

`RAILTRACKS_HOME` always takes priority over directory traversal.

\[

\](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/videos/Visualizer.mp4)

Saving State

By default, all of your runs will be saved to the `.railtracks` directory so you can view them locally. If you don't want that, set the flag to `False`:

```python
import railtracks as rt

# set the configuration globally
rt.set_config(save_state=True)

# or by flow
flow = rt.Flow("my_flow", 
               entry_point=flow_entry,
               save_state=True)
```

## Updating the UI

To install the latest build of the legacy UI, run:

Update UI elements

```bash
railtracks update
```

This updates the legacy build in `.railtracks/ui`. The current visualizer's UI is installed and updated separately.

## Remote Visualization

Note

Would you be interested in observability for your agents in an all in one platform?

Please fill out the following [form](https://forms.gle/mEfBHcdK8qa3SdNn8)

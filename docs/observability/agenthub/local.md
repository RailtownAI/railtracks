# Local Visualization (Legacy)

!!! info "Use the beta visualizer for new projects"
    This page covers the legacy visualizer, which reads the session files
    written by `save_state`. Those files are being replaced by the event
    stream, and so is this UI. For new projects, use the
    [beta visualizer](local_v2.md) (`railtracks viz --beta`). The legacy
    visualizer is still the place to browse [evaluation results](../../evaluations/visualization.md)
    until the beta supports them.

One of the number one complaints when working with LLMs is that they can be a black box. Agentic applications exacerbate this problem by adding even more complexity. Railtracks aims to make it easier than ever to visualize your runs. 

We support:

- Local Visualization (**no sign up required**) 
- Remote Visualization (Ideal for deployed agents)

## Local Development Visualization

The legacy visualizer runs locally with **no sign up required**.

!!! tip "Usage"    

    ```bash title="Install CLI Tool"
    pip install 'railtracks[visual]'
    ```


    ```bash title="Initialize UI and Start"
    railtracks init
    railtracks viz
    ```

This will create a `.railtracks` directory at your project root and open the web app in your browser. Once initialised, railtracks will find that directory automatically, even if you run your agents from a subdirectory, by walking up the folder tree until it locates `.railtracks`.

!!! tip "Running from multiple directories?"
    Run `railtracks init` once from your project root (the same level as your `.git` folder). All subsequent agent runs across the project will resolve to that single `.railtracks` directory regardless of which subdirectory they are launched from.

    If you need a fixed location outside your project (e.g. a shared drive or CI environment), set the `RAILTRACKS_HOME` environment variable to the **parent directory** where `.railtracks` should live:
    ```bash
    export RAILTRACKS_HOME=/path/to/my/project   # .railtracks is created inside here
    ```
    `RAILTRACKS_HOME` always takes priority over directory traversal.


<div class="rt-video-container">
  <video controls style="border-radius: 24px; width: 100%;">
    <source src="https://railtracksstorage.blob.core.windows.net/railtrackswebsite/videos/Visualizer.mp4" type="video/mp4">
  </video>
</div>


!!! tip "Saving State"
    By default, all of your runs will be saved to the `.railtracks` directory so you can view them locally. If you don't want that, set the
    flag to `False`:
    
    ```python
    --8<-- "docs/scripts/visualization.py:saving_state"
    ```

## Updating the UI
To install the latest build of the legacy UI, run:
```bash title="Update UI elements"
railtracks update
```

This updates the legacy build in `.railtracks/ui`. The beta UI is installed and
updated separately.

## Remote Visualization 
!!! Note

    Would you be interested in observability for your agents in an all in one platform?

    Please fill out the following [form](https://forms.gle/mEfBHcdK8qa3SdNn8)

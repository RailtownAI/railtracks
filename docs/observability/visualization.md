# Visualization

One of the number one complaints when working with LLMs is that they can be a black box. Agentic applications exacerbate this problem by adding even more complexity. Railtracks aims to make it easier than ever to visualize your runs. 

We support:

- Local Visualization (**no sign up required**) 
- Remote Visualization (Ideal for deployed agents)

## Local Development Visualization

Railtracks comes with a built-in visualization tool that runs locally with **no sign up required**.

!!! tip "Usage"    

    ```bash title="Install CLI Tool"
    pip install railtracks[cli]
    ```


    ```bash title="Initialize UI and Start"
    railtracks init
    railtracks viz
    ```

This will create a `.railtracks` directory in your current working directory setting up the web app in your web browser


<div class="rt-video-container">
  <video controls style="width: 100%; border-radius: 12px;">
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
As we continue to support the local visualizer and add more features, you may choose to integrate these updated UI components into your local installation by running:
```bash title="Update UI elements"
railtracks update
```

## Remote Visualization 
!!! Note

    Would you be interested in observability for your agents in an all in one platform?

    Please fill out the following [form](https://forms.gle/mEfBHcdK8qa3SdNn8)

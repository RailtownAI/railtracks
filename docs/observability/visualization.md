# Visualization

One of the number one complaints when working with LLMs is that they can be a black box. Agentic applications exacerbate this problem by adding even more complexity. RailTracks aims to make it easier than ever to visualize your runs. 

We support:

- Local Visualization (**no sign up required**) 
- Remote Visualization (Ideal for deployed agents)

## Local Development Visualization

RailTracks comes with a built-in visualization tool that runs locally with **no sign up required**.

### Usage
    

```bash title="Install CLI tTool"
pip install railtracks-cli
```


```bash title="Initialize UI and Start"
railtracks init
railtracks viz
```

This will create a `.railtracks` directory in your current working directory setting up the web app in your web browser


<iframe
    src="https://railtownai.github.io/railtracks-visualizer/iframe.html?globals=&args=&id=components-visualizer-marketing--default&viewMode=story"
    style="width: 99dvw; min-height: 50dvh; border: none; box-sizing: border-box;"></iframe>

!!! tip "Saving State"
    By default, all of your runs will be saved to the `.railtracks` directory so you can view them locally. If you don't want that, set the
    flag to `False`:
    
    ```python
    --8<-- "docs/scripts/visualization.py:saving_state"
    ```

## Remote Visualization

This product is coming soon :smile:. It's gonna knock your socks off. 

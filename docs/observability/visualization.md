#  👀 Visualization

One of the number one complaints when working with LLMs is that they can be a black box. Agentic applications
exacerbate this problem by adding even more complexity. RailTracks aims to make it easier than ever to visualize your
runs.

## 💻 Local Development Visualization

RailTracks comes with a built-in visualization tool that allows you to see your runs once they have completed.

### Usage
    
First install the CLI tool if you haven't already:
```bash
pip install railtracks-cli
```


```bash
railtracks init
```

This will create a `.railtracks` directory in your current working directory setting up the web app.
You can then run your application

```bash
railtracks viz
```

This should open up a web browser window where you can see your runs once they have finished.


![VizDemo.png](../../assets/visualizer_photo.png)

!!! tip "Saving State"
    By default, all of your runs will be saved to the `.railtracks` directory. If you don't want things saved, you can set the
    flag to `False`:
    
    ```python
    import railtracks as rt
    
    rt.set_config(save_state=False)
    # or if you want it scoped to a session
    with rt.Session(save_state=False): ...
    ```

## ☁️ Remote Visualization

However, local viewing is only the beginning of the challenges that face any Agent developer. When you deploy your
application how can you understand what is going on in your Agent?

This product is coming soon 😄

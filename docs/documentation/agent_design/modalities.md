## Text
**_Text_** is the default modality supported in Railtracks. No special operations are needed and you can simply follow the steps outlined in [WHAT]().

## Image
Given the LLM powering your agent, you can pass image inputs to your multimodal agent. The only required step is to construct a `UserMessage` and pass in the parameter `attachment`

```python
rt.llm.UserMessage(
    content="What is in this image?",
    attachment=""
)
```
The `attachment` parameter can be a single `str` or a `list[str]`. We currently support the following:

- Both file and web URLs of the following types: `jpeg`, `png`, `gif`, and `webp`
- `byte64` encoded string of the image 
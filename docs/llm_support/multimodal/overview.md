## Multimodal overview

Traditionally, LLMs map text input to text output. Newer multimodal foundation models (e.g., the GPT‑4o+ family, Claude 3.x/4.x, Gemini 1.5+) can accept additional modalities such as images and, in some cases, audio.

There are also many scenarios where you generate non‑text outputs from text prompts (images or speech) using diffusion models, TTS, or vision‑language models (VLMs) with generation capabilities.

Typical directions include:

- Text → Text (chat, reasoning)
- Image → Text (captioning, OCR, VQA)
- Audio → Text (transcription/ASR)
- Text → Image (image generation/editing)
- Text → Audio (speech synthesis/TTS)
- Image → Image (editing, inpainting, upscaling)
- Audio → Audio (voice conversion)
- Text + Image/Audio → Text/Image/Audio (multimodal reasoning and guided generation)

Below is an illustration of the input/output permutations across the three common modalities. Solid arrows represent common flows; dotted arrows indicate less common ones. The “Fusion” node illustrates multi‑input cases. As you can see things can get complicated quickly and covering all areas would require extra parameter requirements to the public API.

```mermaid
flowchart LR
    %% Inputs
    T_IN[Text]
    I_IN["Image"]
    A_IN["Audio"]
    ADD((+))

    %% Outputs
    T_OUT>"Text"]
    T_OUT2>"Text"]
    I_OUT>"Image"]
    A_OUT>"Audio"]
    A_OUT2>"Audio"]

    %% Paths / Models
    LLM{{"LLM"}}
    TTS{{"Text-to-Audio"}}
    TTS2{{"Text-to-Audio"}}
    MLLM{{"Multimodal LLM"}}
    DIFF{{"Diffusion Models"}}

    %% Connections
    T_IN --> LLM --> T_OUT
    T_IN --> TTS --> A_OUT
    T_IN --> ADD
    I_IN --> ADD
    A_IN --> ADD
    ADD --> MLLM
    MLLM --> DIFF --> I_OUT
    MLLM --> TTS2 --> A_OUT2
    MLLM --> T_OUT2

    %% === COLOR THEMING ===
    %% (Separate comments — not inline)

    classDef text fill:#60A5FA
    classDef image fill:#34D399
    classDef audio fill:#FBBF24
    classDef model fill:#FECACA
    classDef add fill:#BFDBFE

    %% Apply consistent color classes
    class T_IN,T_OUT,T_OUT2 text;
    class I_IN,I_OUT image;
    class A_IN,A_OUT,A_OUT2 audio;
    class ADD add;
    class LLM,VLM,T2I,TTS,TTS2,A2T,MLLM_TI,MLLM_TA,MLLM,DIFF model;

    linkStyle default stroke:grey,stroke-width:1px
```
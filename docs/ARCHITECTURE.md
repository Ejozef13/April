# Audio and interaction architecture

```mermaid
flowchart LR
    Mic[Selected microphone] --> Worklet[Browser AudioWorklet]
    Worklet --> WAV[Bounded mono PCM16 WAV at 16 kHz]
    WAV --> WS[Same-origin WebSocket]
    WS --> Session[Python session / one global job]
    Session --> STT[CPU whisper.cpp process]
    STT --> Transcript[Visible transcript]
    Transcript --> LLM[Local Ollama HTTP stream]
    Clock[Validated clock button] --> Time[Deterministic current_time]
    Time --> Reply[Visible response]
    LLM --> Reply
    Reply --> TTS[CPU Piper process]
    TTS --> Playback[Browser selected output]
    Session --> State[Operation state events]
    State --> Face[Original SVG dog]
    Playback --> Ack[Playback started / ended acknowledgments]
    Ack --> Session
```

The browser owns real capture/playback. The server owns the job lock and operation states. Text bypasses capture/STT. The clock tool bypasses the model; its arguments must be exactly an empty object and its timezone comes from trusted configuration. We deliberately do not pretend the LLM selected the tool.

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> listening: record accepted
    listening --> transcribing: valid bounded WAV received
    idle --> thinking: text or clock request
    transcribing --> thinking: transcript returned
    thinking --> speaking: real playback-start acknowledgment
    thinking --> idle: simulation completes / muted playback canceled
    speaking --> idle: playback ended
    listening --> idle: cancel
    transcribing --> idle: cancel
    thinking --> idle: cancel
    speaking --> error: playback timeout
    thinking --> error: backend failure / timeout
    transcribing --> error: STT failure
    listening --> error: invalid audio / deadline
    error --> idle: retry or cancel
```

Error text remains visible until another action; retry resets state without restarting. Each job has a processing deadline. Browser recording and server recording deadlines prevent a stuck microphone session; playback has its own deadline. Stop immediately releases browser media tracks and playback, cancels the Python task, closes the model stream, terminates only owned speech subprocesses, and releases the global lock. An acknowledgment barrier discards stale server events during browser cancellation.

No LLM-generated shell commands, model tool execution, background task queue, persistent memory, or raw-audio archive exists. The UI describes waiting as waiting; animated expressions never claim to expose model reasoning.

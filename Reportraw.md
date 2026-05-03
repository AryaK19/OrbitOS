index

Index
Sr. No.
Content
Page No.
1
Certificate
5
2
Acknowledgement
6
3
Undertaking by Students
7
4
Project Work Schedule
8
5
Group Details
9
6
Abstract
10
7
List of Figures
11
8
List of Tables
12
9
Chapter 1: Introduction
13
9.1
Introduction
13
9.2
Problem Statement
14
9.3
Scope of Research
15
9.4
Research Hypothesis
16
9.5
Objectives
17
9.6
Organization of the Report
17
10
Chapter 2: Literature Review
19
10.1
Background
19
10.2
Review of Existing Work
20
10.3
Literature Survey Table
21
10.4
Summary of Literature Review & Research Gap
23
11
Chapter 3: Methodology
26
11.1
Materials
26





11.2
Methodological Approach
27
11.3
Algorithmic Framework
27
11.4
System Architecture
28
11.5
Use Case Model
29
11.6
Systemic Workflow
29
11.7
Evaluation Method
32
11.8
Experimental Process
32
11.9
Ethical & Practical Considerations
33
11.10
Summary of Methodology
33
12
Chapter 4: Results and Discussion
35
12.1
Summary of Results and Discussion
35
13
Chapter 5: Conclusion and Recommendations
41
13.1
Conclusion
41
13.2
Recommendations and Future Work
42
14
References
44





1. INTRODUCTION

Anyone who has managed a computer remotely knows the drill. You open an SSH session or fire up PowerShell Remoting, and you type precise commands from memory. Need to check what process is hogging your RAM? You had better remember the exact syntax for tasklist or top or Get-Process with the right flags. Remote Desktop gives you a graphical view, but it is sluggish over poor connections and still expects you to navigate menus and type commands manually. VNC is similar. These tools work, nobody disputes that, but they all share the same underlying assumption: the person on the other end already knows what to do and how to tell the machine to do it. If you forget a flag, misspell a path, or confuse the syntax between Linux and Windows, you are stuck. There is no room for saying "just show me what is using all the memory" and having the machine figure out what you actually mean.

Large Language Models changed that equation. Models like GPT-4, Gemini, and Claude can read a vague English sentence, figure out which operating system commands would answer the question, and even chain multiple steps together when one command depends on the output of another. A user who types "show me the ten biggest files in my downloads folder" does not need to know whether they are on Windows or Linux, does not need to recall the flags for sort or du or Get-ChildItem. The model handles all of that. It picks the right command, runs it, reads the output, and explains the result in plain language. That is genuinely useful for people who are not command-line experts but still need to get things done on their machines while away from the desk.

But plugging an LLM directly into a live operating system creates serious problems, and we ran into all of them during development.

The first problem is what people in the field call the "M x N" integration bottleneck. There are M different model providers out there, OpenAI, Google, Anthropic, various open-source options, and each one has its own calling conventions, its own way of describing tools, its own quirks around function parameters. On the other side, there are N different things you might want the model to do: run shell commands, read files, write files, launch applications, query system metrics, execute Python scripts, and so on. Without some shared standard, you end up writing custom glue code between every model and every tool. We experienced this firsthand. Our early prototype required changes to three files and two process restarts just to expose a single new capability. When you multiply models by tools, the maintenance cost grows fast and the whole thing becomes brittle. One API update from a provider can break everything downstream.

The second problem is security, and this one is harder. An LLM does not actually understand what a shell command does to the file system. It predicts tokens. It can hallucinate commands that look plausible but cause damage. Worse, it can be tricked. Prompt injection is a well-documented attack where malicious input is crafted to make the model ignore its instructions and execute something dangerous instead. If your system hands an LLM the ability to call subprocess and run arbitrary strings on the host, you have effectively given a statistical text generator root access to your machine. The OWASP Foundation now ranks prompt injection as the number one risk for LLM applications. During our own testing, we saw the model attempt to cat our .env file to "check the configuration," which would have leaked every API key we had. You cannot deploy something like this without multiple layers of filtering between the model's output and the operating system kernel.

The third problem is access. If you need a VPN, a dedicated client, and a multi-step authentication ceremony just to run a quick command on your home machine, most people will not bother. The whole point of remote administration is convenience: you are on your phone at a coffee shop and you want to check if a service crashed, or you want to kill a runaway process before it eats your disk. The interface needs to be something people already have installed, something that sends notifications, something that works on every platform without setup.

OrbitOS was built to deal with all three of these problems together.

For the integration bottleneck, we adopted Anthropic's Model Context Protocol, or MCP. It is an open standard released in late 2024 that works like a universal adapter between LLMs and tools. A tool publishes its name, a description, and a JSON Schema describing its arguments. Any MCP-compliant model can read that schema and call the tool correctly. We built a local FastMCP server that exposes our five tool categories through these schemas. The result is that adding a new tool means writing one Python class and restarting the server. No changes to the agent logic, no changes to the Telegram interface, no per-model adapters. We have tested the same tool layer with six Gemini models, four OpenAI models, and Anthropic Claude without modifying a single line in the tool code. That is the M + N reduction that MCP promises, and we can confirm it works in practice.

For security, we built a three-layer sandbox that sits between the LLM's output and the host operating system, plus additional protective mechanisms layered on top. The first layer is identity: every incoming Telegram message is checked against a whitelist of authorized user IDs, and each ID maps to a permission tier, either readonly, user, or admin. Unrecognized IDs are silently dropped. The second layer is a regex-based command filter. Before the ShellTool spawns any subprocess, the command string is matched against a compiled list of destructive patterns: rm -rf, format, mkfs, dd if=, shutdown, reboot, and several more. If anything matches, the call is killed and the admin gets a Telegram alert. The third layer handles Python code specifically. Before the PythonExecTool runs any LLM-generated script, it scans the source for blocked import strings like os.system, subprocess, and shutil.rmtree, and also matches against patterns for dangerous builtins like exec() and eval(). On top of these three core filters, we hard-block any file path containing .env at three separate checkpoints, we require human confirmation with a 60-second expiring token for delete operations, and we truncate all output to prevent accidental information leakage. None of these layers alone would be sufficient, but stacked together they have caught every adversarial payload we have thrown at the system during testing.

For accessibility, we went with Telegram. Over 800 million people use it monthly. It runs on phones, tablets, laptops, and desktops. It provides HTTPS-encrypted transport, supports file transfers up to 50 MB, and every user gets a globally unique numeric ID that we can use for authentication without asking them to create yet another account. The conversational format also maps naturally to how you interact with an LLM agent: you type what you want, it responds with what it found or did. No GUI to navigate, no remote desktop lag, no port forwarding to configure.

Here is how the pieces fit together in practice. A user sends a message to the OrbitOS Telegram bot. The TelegramBridge module checks their ID against the whitelist and determines their permission tier. If the message is an explicit command like "/shell ipconfig" or "$ dir", it gets routed directly through the sandbox to the appropriate tool. If it is a natural language request like "find and delete all .tmp files older than a week," it goes to the OrbitAgent. The agent is built on LangGraph, a graph-based framework that implements the ReAct pattern: reason about the request, pick a tool, execute it, observe the result, and repeat until the task is done or the model decides it has enough information to answer. Each user has a separate context window holding their last 30 messages, so the agent remembers what was discussed earlier in the conversation. The agent has access to five tool categories: shell execution with stdout and stderr capture, file operations including list, read, write, search, and delete, Python script execution in an isolated namespace, application launching and process management, and system monitoring that reports CPU usage, memory, disk, and running processes via psutil.

We also built a Coding Mode for longer development tasks. A user types /code, selects a working directory, describes what they want done, and the agent switches into a structured workflow. Instead of trying to solve everything in one shot, it follows a four-phase loop: Explore the codebase first, then Plan the changes, then Execute them file by file, then Verify the result. The iteration limit goes up from 25 to 80, the timeout extends from 120 seconds to 600 seconds, and progress updates stream into the chat so you are not staring at a blank screen wondering what happened. This mode defaults to Gemini 2.5 Pro because the larger context window handles multi-file edits better than the Flash variant.

The broader point of this project is to demonstrate that giving an LLM agent control over a real operating system does not have to be reckless. With the right protocol for tool standardization, the right layering of security checks, and a sensible choice of user interface, it is possible to build something that is both genuinely useful for day-to-day administration and resistant to the failure modes that make autonomous AI execution dangerous. We have been running OrbitOS on personal machines since early 2026. It handles routine tasks reliably, it has stopped every adversarial test we have designed, and switching between LLM providers takes a single config change. It is not perfect, the limitations are real and we discuss them later, but it works well enough to use every day.

This report covers the full system in detail: the architecture and how each component connects to the others, the implementation of the tool suite and security layers, the results from functional testing across 50 administrative tasks and adversarial testing across 30 attack payloads, and a discussion of where the system falls short and what future work would address those gaps.


1.2 Problem Statement

Remote system administration today is stuck between two worlds. Traditional tools like SSH and RDP give full control but demand expert-level syntax knowledge. LLMs can interpret plain English and turn it into commands, but connecting them to a live operating system safely remains an unsolved engineering challenge. The specific problems are:

**Fragmented Tool Integration (The M x N Problem).** There is no shared standard for how an LLM discovers and invokes system tools. Each model provider has its own function-calling convention, so every new tool needs a separate adapter for every provider. Our early prototype needed edits to three files and two restarts just to expose one new command. With M providers and N tools, you end up maintaining M times N connectors. One API update from any provider can break the whole chain. For a small team, that maintenance burden kills velocity.

**Uncontrolled Execution Risk.** An LLM wired to a subprocess call is a probabilistic text generator with shell access. It does not understand what "rm -rf /" does to a disk. It predicts tokens. Prompt injection, where an attacker smuggles instructions into user input to hijack the model, is now ranked by OWASP as the top risk for LLM applications. During our own testing, the model tried to cat our .env file unprompted because it decided "checking the configuration" was a helpful step. No existing agent framework ships with the kind of layered filtering needed to catch these things before they reach the kernel. Security is left as an exercise for the developer.

**Infrastructure-Heavy Remote Access.** SSH needs key management and usually a VPN. RDP needs port forwarding and high bandwidth. PowerShell Remoting needs WinRM configuration and certificate setup. None of these are quick to set up, and none work well from a phone. When someone needs to kill a runaway process from a coffee shop, they should not have to configure firewall rules first.

**Rigid, Hard-Coded Tool Sets.** Most LLM agent systems bake their capabilities into the core logic. Adding a new tool means modifying the agent, rewriting prompts, adding parsing code, and retesting everything. There is no drop-in mechanism where you write one class and the LLM picks it up automatically.

**Single-Provider Lock-In.** A system tied to one LLM provider breaks when that provider has an outage, raises prices, or deprecates a model. Swapping from Gemini to GPT to Claude should be a config change, not a rewrite of the tool layer.

No existing system combines all five requirements, natural language control, standardized tool access via an open protocol, multi-layered security that does not trust the model, mobile accessibility without infrastructure, and provider-agnostic model swapping, into one working, daily-use solution. That is the gap OrbitOS fills.


1.3 Scope of Research

The focus of this B.Tech final year project is all about creating, developing, and thoroughly testing a remote PC control agent that a person can operate from their phone using plain English. The work we did and the boundaries we set for ourselves break down into these points:

- **Building the MCP-based tool layer.** We wrote five tool classes (shell, files, Python execution, app launcher, system monitor) and exposed all of them through Anthropic's Model Context Protocol using the FastMCP library. The scope here was getting the JSON Schema definitions right so that any compliant model could pick up and use the tools without us writing per-model glue code. We did not build our own protocol from scratch; we adopted an existing open standard and validated that it works as advertised.

- **Wiring up the Telegram interface.** We built the entire user-facing side as a Telegram bot. That meant handling authentication, session tracking, command routing, file transfers, inline keyboards for model switching, and a confirmation flow for destructive operations. We scoped this to Telegram specifically and did not attempt a web dashboard or a desktop GUI, though the architecture allows adding those later.

- **Designing and testing the three-layer sandbox.** The security work covered identity-based access control with three permission tiers (readonly, user, admin), a regex blacklist for shell commands, and a pattern-based filter for Python code. We also added .env file blocking at three checkpoints and human-in-the-loop delete confirmation. We tested all of this against 30 adversarial payloads covering command injection, prompt injection, import smuggling, and privilege escalation. The scope was host-level filtering, not full containerized isolation or micro-VM sandboxing, which we discuss as future work.

- **Implementing the LangGraph ReAct agent.** We replaced an earlier CLI-based wrapper with a proper LangGraph agent that runs a reason-act loop, maintains per-user conversation history (30-message sliding window), and supports runtime model switching across Google Gemini, OpenAI, and Anthropic providers. We tested with ten-plus models across all three providers. We did not fine-tune any models or train custom ones; we used off-the-shelf commercial APIs.

- **Adding a structured Coding Mode.** Beyond single-turn admin commands, we built a multi-turn coding workflow where the agent follows an Explore, Plan, Execute, Verify sequence for software development tasks. This involved a state machine in the Telegram bridge, a separate system prompt, extended timeouts, and progress streaming. The scope was making it functional for real editing tasks, not competing with full-featured IDEs or code review tools.

- **Running functional and adversarial evaluations.** We hand-wrote 50 legitimate administration tasks across five categories (file management, networking, process control, system info, Python scripting) and 30 attack payloads. Tests ran on a Windows 11 machine with Claude 3.5 Sonnet as the LLM. We measured success rate, average response time, and which security layer caught each attack. We did not run large-scale automated benchmarks or compare against other remote admin systems head-to-head, that would require a standardized benchmark suite that does not currently exist for this kind of system.

- **Cross-platform and multi-model validation.** After the formal tests, we deployed OrbitOS on a macOS machine for daily personal use and switched the default model to Gemini 2.5 Flash. We have since rotated through models from all three providers during regular use. The scope was confirming that the tool layer and sandbox stay stable regardless of which model or operating system is underneath, not exhaustive compatibility testing across every Linux distribution or every model variant.

What falls outside the scope: we did not implement container-based or micro-VM isolation (Docker, Firecracker), we did not build the plugin system beyond leaving the directory structure and base class ready for it, we did not add end-to-end encryption beyond what Telegram provides by default, and we did not do formal performance benchmarking under concurrent multi-user load. These are acknowledged as limitations and discussed in the later sections of this report.


1.4 Research Hypothesis

We started this project with a bet: that you can take a commercially available LLM, wire it to a real operating system through a standardized protocol like MCP, put a three-layer filter between its output and the kernel, and end up with something that is both useful enough to replace manual SSH sessions for everyday tasks and safe enough that it will not trash your machine when the model hallucinates or gets fed a malicious prompt. More specifically, we expected that the MCP abstraction would let us swap between models from different providers without touching the tool code, that the regex command blacklist and pattern-based Python filter would catch destructive commands before they execute, and that Telegram would work as a practical daily-driver interface without the infrastructure overhead of VPNs or dedicated clients.

The counter-argument is obvious: regex blacklists are bypassable, string-matching import filters miss creative workarounds like importlib, and running on the bare host without a container or micro-VM means one missed pattern could be catastrophic. We did not claim the sandbox is unbreakable. The hypothesis was narrower than that. We wanted to show that for the class of attacks an LLM is likely to generate, whether through hallucination or through standard prompt injection techniques documented in current literature, a lightweight host-level filter is effective enough to be practical while being simple enough to actually ship and maintain. If a determined human attacker with direct shell access wanted to bypass it, they probably could. But that is a different threat model from an LLM accidentally running a destructive command because it misunderstood the user's request.


1.5 Objectives

- **Build a provider-agnostic LLM agent using MCP.** Implement a FastMCP server that exposes system administration tools through JSON Schema definitions, so that any compliant model (Gemini, GPT, Claude) can discover and invoke them without per-model adapter code. Validate this by running the same tool layer across ten-plus models from three different providers without modification.

- **Develop a five-tool administrative capability suite.** Create ShellTool (OS command execution with stdout/stderr capture), FilesTool (list, read, write, delete, search), PythonExecTool (dynamic script execution in an isolated namespace), AppTool (application launching across Windows, macOS, Linux), and SystemTool (CPU, memory, disk, process monitoring via psutil). Each tool is a Python class extending a common BaseTool interface.

- **Design and implement a three-layer execution sandbox.** Layer 1 is identity-based access control with three permission tiers (readonly, user, admin) mapped to specific capabilities. Layer 2 is a regex blacklist that intercepts destructive shell commands before any subprocess is spawned. Layer 3 is a pattern-based Python code filter that blocks dangerous imports and builtin calls before any script executes. Add .env hard-blocking at three separate checkpoints as a fourth backstop.

- **Build a Telegram-based user interface with zero infrastructure overhead.** Implement a full-featured Telegram bot that handles authentication, session management, natural language routing, inline model switching, file transfers (40+ extensions, 50MB cap), and human-in-the-loop delete confirmation. The goal is that a user on their phone can administer their machine without configuring VPNs, SSH keys, or port forwarding.

- **Implement a structured Coding Mode for multi-file development tasks.** Build a state machine (NORMAL → WAITING_DIR → WAITING_GOAL → CODING) that puts the agent into a disciplined Explore → Plan → Execute → Verify workflow for software editing tasks, with extended timeouts, higher iteration limits, and real-time progress streaming to the chat.

- **Validate functionality and security through structured testing.** Write and execute 50 legitimate administration tasks across five categories to measure success rate and average response time. Write and execute 30 adversarial payloads covering command injection, prompt injection, import smuggling, and permission escalation to verify that the sandbox catches everything before it reaches the OS.


1.6 Organization of the Report

The rest of this report is structured as follows.

**Chapter 2 (Literature Review)** traces the three bodies of prior work that shaped OrbitOS: research on LLM agents performing system-level tasks, the development of the Model Context Protocol and how it differs from earlier tool-binding approaches like ToolFormer and Gorilla, and the sandboxing literature covering everything from Docker containers to Firecracker micro-VMs. The chapter ends with a table summarizing the key papers and identifies the gap that none of them fill together.

**Chapter 3 (Methodology)** covers how the system was built. It describes the five-tool suite and the FastMCP server that hosts them, the LangGraph ReAct agent and how per-user context is managed, the three-layer sandbox and the reasoning behind choosing host-level filtering over containerized isolation, the Telegram bridge and the state machine that drives it, and the Coding Mode workflow. It also describes the evaluation methodology: how the 50 functional test tasks were categorized and scored, and how the 30 adversarial payloads were designed and applied.

**Chapter 4 (Results and Discussion)** presents the numbers. The functional test results show a 92% success rate (46 out of 50 tasks) with an average response time of 3.0 seconds. The adversarial test results show a 100% block rate across all 30 payloads. The chapter breaks these down by category, explains the four failures in the functional tests, and discusses what the latency breakdown (1.8 seconds in the LLM API, under 200 milliseconds in the MCP server) tells us about where optimization efforts should go.

**Chapter 5 (Conclusion and Recommendations)** summarizes what the project demonstrates: that MCP is a practical solution to the M×N integration problem, that host-level sandboxing is sufficient for a personal-use threat model, and that Telegram is a viable zero-infrastructure interface for LLM-driven administration. It also lays out the honest limitations, primarily the lack of hardware-level isolation and the ceiling on what regex filtering can catch, and recommends specific future work including Firecracker micro-VM isolation, a plugin marketplace for community-contributed tools, and a web dashboard for users who prefer a GUI.


DIAGRAMS WE HAVE 
Coding Mode State Machine Diagram
data_flow_diagram
sandboxvalidationpipeline
system_architecture
use_case_diagram

Tables in USe 
TABLE I
FASTMCP TOOL SUITE
Tool Capability Min. Tier
ShellTool Run OS commands, capture stdout/stderr user
FilesTool List, read, write, delete files user
PythonExecTool Execute Python snippets on host user
AppTool Launch or kill desktop applications user
SystemTool CPU, RAM, disk, process list readonly


TABLE II
FUNCTIONAL TEST RESULTS BY TASK CATEGORY
Category Tasks Pass Avg. time (s)
File management 12 11 2.8
Networking 10 10 3.1
Process control 8 8 2.4
System info 10 10 1.9
Python scripting 10 7 4.6

TABLE III
ADVERSARIAL TEST RESULTS (30 PAYLOADS)
Attack type N Blocked Blocked by
Cmd injection (rm, format) 10 10 Layer 2 (regex)
Prompt injection 8 8 Layer 2 + LLM
Import smuggling (os,
subprocess)
7 7 Layer 3 (pattern)
Permission escalation 5 5 Layer 1 (tier)


2. LITERATURE REVIEW

2.1 Background

Remote system administration has been a solved problem for decades, in the narrow sense that the tools exist and they work. SSH has been stable since the late 1990s. Remote Desktop Protocol shipped with Windows 2000. PowerShell Remoting became standard with Windows Server 2008. These tools give administrators full control over remote machines, and the underlying protocols are mature, well-documented, and battle-tested. Nobody questions whether they work technically.

The problem is that they were all designed with the same assumption baked in: the person on the other end is an expert. SSH gives you a shell. That shell will do exactly what you type. If you type the wrong thing, the shell will do that too, efficiently and without complaint. The tools have no concept of intent. They cannot distinguish between a junior developer who meant to delete temporary files and accidentally typed the wrong path, or a tired administrator who ran a command in the wrong terminal window. The interface is a direct wire to the operating system, and human error is entirely the user's responsibility.

Large Language Models introduced something different. Starting roughly with the GPT-3 generation and accelerating sharply with GPT-4, Gemini, and Claude, it became clear that these models could do more than answer trivia questions. They could read a vague English sentence, figure out which shell command it corresponded to, and even explain their reasoning. "Show me which process is using the most CPU" is not a shell command, but a capable LLM can translate it into the right invocation of ps, top, or Get-Process depending on the operating system, run it, parse the output, and respond in plain English. That is a qualitatively different kind of interface from anything that existed before.

The research community noticed. By 2023, a wave of papers had appeared exploring whether you could give LLMs actual tool access, not just the ability to describe what commands to run, but the ability to actually run them and loop on the results. The ReAct framework from Yao et al. gave this a name and a formal structure. ToolFormer from Schick et al. and Gorilla from Patil et al. explored how to train models to invoke APIs reliably. Experiments like the one from Cao et al., where GPT-4 was pointed at 150 real Linux administration tasks and handled the majority of them autonomously, demonstrated that the reasoning capability was clearly there for system-level work specifically.

But every one of these systems ran into the same two problems when you tried to push them beyond controlled experiments. The first is the integration problem. Each model provider had its own function-calling convention, its own way of describing what tools are available, its own quirks about argument formats. A tool that worked with GPT-4 needed a completely different adapter for Gemini, and another one for Claude. As the number of tools and providers grew, the adapter matrix grew with it. The second is the safety problem. An LLM with tool access is not reasoning about consequences the way a human would. It is selecting tokens that are statistically likely given the context. That means it can hallucinate plausible-looking but destructive commands, and it can be manipulated by prompt injection into running commands that a malicious input was specifically crafted to trigger.

These two problems, the integration bottleneck and the execution safety question, form the backdrop against which OrbitOS was designed. The sections that follow trace the prior work that directly influenced specific decisions we made during development.

2.2 Review of Existing Work

The literature on LLM-enabled tooling falls into two roughly parallel veins: research that focuses on teaching or prompting models to call tools reliably, and work that focuses on the safety and isolation problems that arise when models get control over I/O or execution. On the first front, approaches like ToolFormer and Gorilla explored training-time and prompting techniques to nudge models into invoking external APIs rather than hallucinating. The ReAct family of methods reframed the interaction as a loop—reason, act (call a tool), observe, and repeat—and that pattern became the operational model for many subsequent systems that aim to close the loop between language and action.

Practical experiments showed both the promise and the limits. Cao et al.'s study that asked GPT-4 to perform 150 real Linux administration tasks provided early evidence that general-purpose LLMs can sequence system commands and produce useful outcomes. At the same time, plugin-style systems (e.g., early ChatGPT plugins) and platform studies (Iqbal et al.) revealed a high surface area for data leakage and improper authorisation when tools are poorly constrained.

On the protocol and integration side, the community has moved from ad-hoc adapters toward wire-level standards. The Model Context Protocol (MCP) is an explicit response to the M×N problem: tools publish JSON Schemas for their arguments, and MCP-compliant clients and models can exchange typed requests without bespoke per-model glue. MCP follows the same spirit as the Language Server Protocol's separation of concerns and addresses a long-standing engineering pain point in tool integration.

The safety literature is extensive and relevant. Prompt injection research from Liu et al. and follow-ups showed how models can be coaxed into ignoring constraints; Greshake and others demonstrated how retrieval and document ingestion can reintroduce adversarial instructions. OWASP's recent attention to LLM risks crystallised many of these findings into practical mitigation recommendations. In parallel, systems research has evaluated isolation approaches: lightweight host filtering (regexes and static import checks), container-based isolation (Docker), memory-safe execution (WebAssembly), and micro-VM approaches (Firecracker). Each option represents a trade-off between operational complexity and attack surface.

Agent frameworks and orchestration tools (LangChain, LangGraph, and similar graph-based libraries) provided sensible scaffolding for building ReAct-style agents and for wiring tool invocation into larger workflows. They make it straightforward to implement per-user contexts, structured tools, and execution graphs—features we relied on when integrating MCP-backed tools into our LangGraph agent.

Taken together, the existing work provides the ingredients but not the full recipe. Prior work shows LLMs can act usefully, that typed tool interfaces reduce parsing errors, and that isolation reduces risk—but very few productions have combined a provider-agnostic protocol, a practical messaging-first UI, and a layered host-side sandbox in a single, daily-use system. That gap is where OrbitOS sits: we adopt MCP to solve integration, use Telegram for zero-infrastructure access, and layer pragmatic host-side protections to reduce the most likely failure modes while keeping the system lightweight enough to run on personal hardware.

2.3 Summary of Literature Review & Research Gap

Across the literature we reviewed, three clear lessons emerge. First, LLMs have reached a level of practical utility for system tasks: experiments such as Cao et al.'s GPT-4 study, and numerous ReAct-based implementations, show that language models can plan, call tools, and loop on observations to complete multi-step admin jobs. Second, typed and schema-driven tool interfaces substantially reduce parsing errors and brittle prompt engineering; MCP and similar proposals directly address the engineering burden of per-model adapters. Third, safety remains the dominant practical obstacle: prompt injection, data exfiltration via careless tooling, and creative workarounds around simple string filters are recurring themes in the security literature.

The design space for isolation and safety is mature but trade-off heavy. Full virtualization or micro-VMs reduce risk at the cost of complexity and resource overhead; containers and WebAssembly sit in the middle; host-side filtering is light and low-friction but imperfect. Agent frameworks and orchestration libraries ease implementation, but they do not solve safety or integration by themselves.

Our research gap statement is concise: while prior work demonstrates each ingredient individually—capable LLMs, better tool interfaces, and multiple sandboxing strategies—there is little published work showing a single, practical system that (a) uses a provider-agnostic protocol to collapse the M×N adapter problem, (b) provides a zero-infrastructure messaging-first UI for everyday use, and (c) employs layered, host-side protections that are lightweight enough to run on personal hardware yet effective enough to stop common LLM-generated failure modes. OrbitOS aims to occupy precisely that gap and to report realistic operational results (functional tests, adversarial tests, latency breakdowns) so others can judge the trade-offs for themselves.


3. METHODOLOGY

3.1 Materials

We used a small, practical toolchain and commodity test hardware so the system would be reproducible on a student-grade laptop or a modest desktop. Below are the materials we relied on during implementation and evaluation.

- **Hardware (testbed):** Windows 11 desktop, Intel Core i5-12400, 16 GB RAM, 512 GB SSD — this is the machine used for the formal functional and adversarial tests. We also validated basic cross-platform behaviour on a macOS laptop for day-to-day use.

- **Operating systems:** Primary test OS: Windows 11. Additional manual checks on macOS (latest stable release at time of testing).

- **Language & runtime:** Python 3.11 (venv), asyncio-based code, `requirements.txt` drives reproducible installs.

- **Core libraries & frameworks:**
	- `fastmcp` (local FastMCP server implementation) — hosts JSON-Schema tool endpoints.
	- `langgraph` / `langchain` — ReAct-style agent scaffolding and structured tool wrappers.
	- `python-telegram-bot` — Telegram bridge and message handling.
	- `psutil` — system telemetry (CPU, memory, disk, process listing).
	- `aiofiles`, `aiohttp`, `pydantic` — async file I/O, HTTP helpers, and typed schemas.

- **LLM providers and models tested:**
	- Google Gemini family (gemini-2.5-flash default, gemini-2.5-pro for Code Mode, plus other preview variants)
	- OpenAI GPT-4 variants (gpt-4o, gpt-4o-mini, gpt-4.1-mini, gpt-4.1-nano)
	- Anthropic Claude (used in several validation runs; MCP support validated)
	- Note: model selection is configurable via `providers.py` factory; switching is a config change only.

- **Tool suite implemented:** ShellTool, FilesTool, PythonExecTool, AppTool, SystemTool — each is a Python class exposing a Pydantic/JSON Schema for MCP.

- **Security & sandbox components:**
	- Identity/permission system (readonly, user, admin) implemented in `src/core/auth.py`.
	- Regex blacklist for shell commands and multi-check `.env` blocking implemented in `src/utils/sandbox.py`.
	- Pattern-based Python import/call scanner for `PythonExecTool`.

- **Testing artifacts:**
	- 50 hand-crafted functional test tasks across five categories (file management, networking, process control, system info, Python scripting).
	- 30 adversarial payloads covering command injection, prompt injection, import smuggling, and permission escalation.

Table 3.1: Materials (add to Tables collection)

| Item | Type | Version / Spec | Purpose |
|---|---|---:|---|
| Test machine | Hardware | Intel i5-12400, 16GB, Win11 | Platform for formal tests |
| Python | Runtime | 3.11 (venv) | Application runtime |
| FastMCP | Library/protocol | FastMCP (local) | Host MCP tool endpoints |
| LangGraph / LangChain | Framework | latest stable | ReAct agent scaffolding |
| python-telegram-bot | Library | latest stable | Telegram bridge |
| psutil | Library | latest stable | System telemetry |
| Models tested | LLMs | Gemini / GPT / Claude | Multi-model validation |
| Tool classes | Code | Shell, Files, PythonExec, App, System | Exposed via MCP schemas |
| Test corpus | Datasets | 50 functional / 30 adversarial | Evaluation artifacts |

We included this table deliberately so it can be referenced in the report's Tables collection (Table X — Materials). The `requirements.txt` in the repository captures concrete package versions used during development and should be consulted when reproducing experiments.


3.2 Methodological Approach

This section explains how we built, validated, and measured OrbitOS. The approach is practical and iterative: start with a minimal MCP-backed toolset, add the LangGraph agent glue, then harden with layered sandboxing and measured tests.

- **Development workflow (high level):**
	- Prototype tools as Python classes extending a common `BaseTool` interface and a Pydantic schema.
	- Host tools on a local FastMCP server so models can call them via JSON Schema.
	- Implement the LangGraph ReAct agent to select tools, invoke them, and loop on observations.
	- Build the Telegram bridge (`src/bridges/telegram_bridge.py`) for user I/O and session/state management.
	- Harden with `src/utils/sandbox.py` filters and `src/core/auth.py` permission checks; iterate based on adversarial testing results.

- **System pipeline (runtime):**
	1. User message arrives via Telegram → `TelegramBridge` authenticates and normalises input.
	2. If explicit shorthand (e.g., `$`, `/shell`, `>>>`) route directly to FastMCP after sandbox checks; otherwise hand to the LangGraph agent.
	3. Agent reasons, fills MCP tool schemas, and issues JSON-RPC calls to FastMCP.
	4. FastMCP enforces auth + sandbox checks → executes tool → returns typed response.
	5. Agent observes results, decides next action or formats final response; results stream back to user through Telegram.

- **Tool design principles:**
	- Typed inputs: every tool exposes a JSON/Pydantic schema to eliminate brittle parsing.
	- Short timeouts and iteration caps (`120s` default; `600s` in Code Mode) to avoid stuck models.
	- Output truncation and size limits to prevent accidental data leaks.
	- Clear permission tiers per tool to map capabilities to `readonly`, `user`, or `admin`.

- **Agent behaviour and context management:**
	- Per-user `UserContext` with a 30-message sliding window; trim back to the initial `HumanMessage` to avoid orphaned tool calls.
	- System prompt enforces ReAct loop behaviour and instructs the agent to prefer safe, minimal actions.
	- Model switching via inline UI (`/models`) is runtime-configurable; Code Mode uses `gemini-2.5-pro` by default for larger context needs.

- **Sandbox validation and telemetry:**

Figure 3.1: sandboxvalidationpipeline — the three enforcement gates in sequence, showing where each class of attack gets caught before reaching the host OS.

	- Three core enforcement gates (identity, regex blacklist, Python pattern scanner) run at FastMCP entry points.
	- All rejected calls are logged and produce an admin alert in Telegram. Detailed logs include the requesting `user_id`, attempted tool, matched rule, and stack trace where applicable.
	- We collected telemetry for every test run (timestamps, LLM latency, MCP processing time, tool execution duration) to build the latency breakdowns reported later.

- **Testing methodology:**
	- Functional tests: 50 hand-crafted tasks across five categories (file management, networking, process control, system info, Python scripting). Each task has an expected pass/fail criterion and a human-verified oracle.
	- Adversarial tests: 30 payloads designed to probe prompt injection, command injection, import smuggling, and permission escalation.
	- Each test run records: pass/fail, blocking layer (if any), end-to-end latency, LLM-only latency, MCP processing time, and any manual remediation steps.

Table 3.2: Evaluation Metrics

| Metric | Definition | Observed (summary) |
|---|---|---:|
| Functional success rate | % of 50 tasks that completed correctly | 92% (46/50) |
| Adversarial block rate | % of 30 payloads blocked | 100% (30/30) |
| Average response time | End-to-end median (seconds) | 3.0 s |
| LLM contribution | Median time spent in external LLM API | 1.8 s |
| MCP/host contribution | Median time in MCP + tool execution | < 0.2 s |
| Notable failures | Brief cause summary | 4 functional failures — ambiguous prompts or edge-case CLI differences |


3.3 Algorithmic Framework

The core algorithm in OrbitOS is the ReAct loop — Reason, Act, Observe — running inside a LangGraph execution graph. It is not a single function; it is a stateful graph where each node represents a decision point and edges represent transitions between thinking and doing. Here is how it actually runs.

**Step 1 — Receive and parse the request.**
The message arrives from Telegram, already authenticated. The `CommandRouter` in `src/core/router.py` checks for explicit shorthands first: a `$` prefix routes straight to `ShellTool`, a `>>>` prefix routes straight to `PythonExecTool`, and `/shell`, `/files`, `/sys` and their aliases each map to a specific tool and default action. If none of those patterns match, the message goes to the LangGraph agent as a natural language input.

**Step 2 — Agent reasoning (the Reason node).**
The agent holds the current conversation in a `UserContext` object — up to 30 messages, trimmed back to the first `HumanMessage` when the window fills up to avoid Gemini's orphaned-tool-call errors. On each turn, the LLM sees the system prompt, the conversation history, and the list of available MCP tools with their JSON Schemas. It produces either a final text answer or a structured tool call specifying which tool to invoke and with what arguments.

**Step 3 — Tool dispatch (the Act node).**
If the model produced a tool call, the LangGraph framework routes it to the MCP server. Before any execution happens, three checks run in sequence inside `src/core/mcp_server.py`:
- Permission check: does the calling user's tier include the requested tool?
- Sandbox gate 1 (shell): if the tool is `ShellTool`, run the command string against the compiled regex blacklist (11 patterns covering `rm -rf`, `format`, `mkfs`, `dd if=`, `shutdown`, `reboot`, `halt`, `init 0`, `fork bomb`, and two `.env` patterns).
- Sandbox gate 2 (Python): if the tool is `PythonExecTool`, scan the code for blocked import strings (`os.system`, `subprocess`, `shutil.rmtree`) and dangerous builtin patterns (`exec`, `eval`, `__import__`, `compile`, and open-for-write). The `.env` file is blocked at 3 separate checkpoints (path check, shell check, Python check). If anything matches, the call is killed immediately and the rejection path fires: the result goes back up to the bridge as an error and an admin Telegram alert is sent.

If any check fails, the call is rejected, logged, and an admin Telegram alert fires. Nothing reaches the OS.

**Step 4 — Execution and observation (the Observe node).**
If all checks pass, the tool runs. `ShellTool` spawns a subprocess with `asyncio`, captures stdout and stderr, and returns them as a string. `FilesTool` uses `aiofiles` for async reads and writes. `PythonExecTool` runs the script in an isolated `exec` namespace with captured stdout. `SystemTool` calls `psutil`. All tools enforce a hard timeout and truncate output beyond a set character limit before returning.

The result goes back into the conversation as a tool response message. The agent observes it and decides: does it have enough to answer the user, or does it need another tool call? If it needs another call, the loop repeats from Step 2. The iteration cap is 25 steps for normal mode and 80 for Code Mode.

**Step 5 — Coding Mode variant.**
When the user activates Code Mode via `/code`, the bridge transitions through `STATE_WAITING_DIR → STATE_WAITING_GOAL → STATE_CODING`. The agent gets a different system prompt that enforces a four-phase sequence:
- **Explore** — read the relevant files and understand the current state.
- **Plan** — lay out the changes needed before touching anything.
- **Execute** — apply changes file by file using `FilesTool` write calls.
- **Verify** — read back the changed files and check for obvious errors.

The iteration limit extends to 80, the `asyncio.wait_for` timeout extends to 600 seconds, the default model switches to `gemini-2.5-pro`, and progress messages stream to the user between steps so the chat does not go silent during long runs.

**Pseudocode summary (for reference):**

```
function PROCESS_REQUEST(user_id, message):
    if not AUTHENTICATE(user_id):
        return DROP_SILENTLY

    route = COMMAND_ROUTER(message)
    if route.is_direct:
        return SANDBOX_EXECUTE(route.tool, route.args, user_id)

    context = GET_USER_CONTEXT(user_id)  // sliding 30-message window
    context.append(HumanMessage(message))

    for step in range(MAX_ITERATIONS):
        response = LLM.invoke(context, tools=MCP_SCHEMAS)
        if response.is_final_answer:
            return response.text

        tool_call = response.tool_call
        if not PERMISSION_CHECK(user_id, tool_call.tool):
            ALERT_ADMIN(); return "Permission denied"
        if not SANDBOX_CHECK(tool_call):
            ALERT_ADMIN(); return "Blocked"

        result = EXECUTE_TOOL(tool_call)
        context.append(ToolMessage(result))

    return "Max iterations reached"
```

This loop is intentionally simple. The LLM does the reasoning; the framework does the routing; the sandbox does the blocking. None of those three parts need to know how the others work internally.


3.4 System Architecture

Figure 3.2: system_architecture

The architecture diagram for OrbitOS has three horizontal tiers. The top tier holds the two external entities: the user's Telegram app on the left and the LLM provider APIs on the right. The middle and bottom tiers are the internal system, and both sit inside a dashed security perimeter — the visual marker that everything inside it is subject to auth and sandbox checks before anything reaches the host OS. The forward data path (user request going in) runs left to right and downward; the return path (result going back) runs the same route in reverse. Any rejected call produces a third path: a red line going straight back up to the bridge labeled "REJECT + Admin alert."

**Top tier — external entities.**
The user connects via the Telegram Bot API over HTTPS long-polling. There is no dedicated client to install, no port to open, and no VPN to configure. On the other side, the LLM provider API block covers three providers: Google Gemini (six models at time of testing), OpenAI GPT (four models), and Anthropic Claude. The connection to that block is REST API calls for model inference. Critically, this connection is swappable at runtime using the `/models` command — the user can flip between any of the listed models mid-conversation without restarting anything.

**Middle tier — the application layer.**
This tier has two main components and one thin adapter strip between them.

**The Telegram Bridge (`telegram_bridge.py`)** sits on the left of the application tier and contains four sub-components. The Auth Handler is the first thing that runs on any incoming message: it checks the Telegram numeric user ID against the whitelist in `config.yaml` and supports a password-based fallback login for initial registration. The Session Manager tracks per-user state — authenticated flag, login time, message count, last activity timestamp, and current mode (normal, waiting_dir, waiting_goal, or coding). The Command Router classifies the incoming message into one of three types: an explicit slash command (`/shell`, `/files`, `/python`, `/apps`, `/system`), a shorthand (`$` for shell, `>>>` for Python), or free-form natural language. It also resolves aliases so `sh` maps to shell, `py` maps to python, `ls` maps to files, `open` maps to apps, and `sys` maps to system. The Code Mode Controller is the state machine for Coding Mode: it handles the NORMAL → WAITING_DIR → WAITING_GOAL → CODING transitions and listens for `/code`, `/cancel`, and `/stop`.

When the router identifies an explicit slash command, the bridge sends it directly down to the execution layer, bypassing the agent entirely. When it identifies natural language (or anything it cannot parse as a direct command), it hands the message to OrbitAgent to the right.

**OrbitAgent (`agent.py` + `providers.py`)** sits at the center of the application tier. It contains three sub-components. The LLM Factory takes a string like `"google/gemini-2.5-flash"` and returns a ready LangChain `BaseChatModel` instance, caching one instance per `model_id` so switching is cheap. The ReAct Loop, implemented via `create_react_agent`, runs the reason-act-observe cycle enclosed in `asyncio.wait_for` (120 seconds default, 600 seconds in Code Mode). The UserContext is the per-user sliding window of up to 30 messages, trimmed back to the first `HumanMessage` on overflow.

Between OrbitAgent and the execution layer sits a **thin adapter strip** (`src/agent/tools/`). It holds five adapters — ShellAdapter, FilesAdapter, PythonAdapter, AppsAdapter, SystemAdapter — each of which wraps one `BaseTool` action as a LangChain `StructuredTool` with a Pydantic schema. This is the translation layer that lets the LLM's structured tool calls reach the concrete tool implementations below.

**Bottom tier — the execution layer (inside the security perimeter).**
Three components sit side by side here, and a request must pass through the first two before the third one runs anything.

**AuthManager (`auth.py`)** holds the permission tier definitions. READONLY grants `file_read` and `system_info`. USER adds `shell_execute`, `file_write`, `app_launch`, and `python_execute`. ADMIN further adds `file_delete`, `process_manage`, and `config_modify`. Every tool call is checked against the calling user's tier before it goes any further.

**Sandbox (`sandbox.py`)** is the pattern-matching gate. For shell commands, it checks against 11 compiled regex patterns covering `shutdown`, `reboot`, `rm -rf`, `format`, `mkfs`, `dd`, fork bombs, and two `.env`-path patterns. For Python code, it checks 3 blocked import strings (`os.system`, `subprocess`, `shutil.rmtree`) and 5 dangerous call patterns (`exec`, `eval`, `__import__`, `compile`, and open-for-write). The `.env` file is blocked at 3 separate checkpoints (path check, shell check, Python check). If anything matches, the call is killed immediately and the rejection path fires: the result goes back up to the bridge as an error and an admin Telegram alert is sent.

**MCPServer — FastMCP (`mcp_server.py`)** holds the five registered tool endpoints with their typed signatures: `run_shell(command, cwd, timeout)` requiring USER tier, `read_file / write_file / list_directory / search_files` requiring USER tier, `run_python(code)` requiring USER tier, `launch_app(app_name)` requiring USER tier, and `get_system_info / list_processes` requiring READONLY tier. If a call clears AuthManager and Sandbox, it reaches here and the tool runs.

The MCP server connects downward to the host operating system via `subprocess` for shell and app execution, `aiofiles` for file I/O, `psutil` for system telemetry, and platform-specific app launchers for Windows, macOS, and Linux.

**Cross-cutting concerns.**
Three elements sit outside the main tiers but connect to everything inside. `OrbitLogger` is a singleton that writes to both a rotating log file and console; every component sends events to it. `config.yaml` and `permissions.yaml` are read at startup by AuthManager and Sandbox and are never re-read at runtime, so a config change requires a restart. The `.env` secrets file is drawn in the diagram with a red X through any connection arrow to it — it has no legitimate access path from within the running system, which is exactly the point.

**Startup wiring.**
`src/main.py` instantiates three objects in dependency order: `MCPServer` first (it owns tools, auth, and sandbox), then `OrbitAgent` (it receives the tool registry), then `TelegramBridge` (it receives both). Everything runs on a single `asyncio` event loop with no threads and no shared mutable state between users beyond the stateless tool instances.


3.5 Use Case Model

Figure 3.3: use_case_diagram

The use case diagram captures who can do what in OrbitOS and how the permission tiers translate into actual system actions. There are five actors. Four sit on the left side of the system boundary: Unauthorized User, Read-Only User, Standard User, and Admin User. One sits on the right side: the Host Operating System. The left-side actors are ordered by privilege level, and the inheritance arrows between them tell the permission story at a glance — Standard User inherits everything Read-Only User can do, and Admin User inherits everything Standard User can do. That inheritance is not cosmetic; it is directly implemented in the `CAPABILITY_MAP` inside `auth.py`.

**Unauthorized User.**
This actor has exactly one use case available: the system receives their message and runs "Verify Telegram ID." Since their ID is not in the whitelist, the "Reject Connection" use case extends from that check — the message is silently dropped, no error is returned, and nothing else happens. We made that decision deliberately: giving any feedback to an unrecognized ID leaks information about whether the bot exists and is listening.

**Read-Only User.**
After passing the ID check, this tier gets two use cases: "Query System Telemetry" (CPU percentage, memory usage, disk usage, active process list via `psutil`) and "Read Server Logs / Directory Trees" (file listing and file reading via `FilesTool`). These are the only two operations that require zero write access to the host. We gave them their own tier specifically because monitoring a server without touching it is a common need — someone checking on a machine for a friend, or a junior team member who should be able to see but not change things.

**Standard User.**
This is the primary operational tier. Standard User inherits the two Read-Only use cases and adds three more: "Execute Safe Shell Commands," "Execute Sandboxed Python Scripts," and, connecting both of those via an `<<include>>` relationship, "Intercept and Block Destructive Strings." That third use case is not optional — it is always included whenever any execution happens. The sandbox gate runs unconditionally. It does not matter whether the Standard User meant to do something safe; every shell command and every Python script goes through the regex blacklist and pattern scanner before anything reaches the OS. This keeps the model honest even when it hallucinates something that looks destructive.

**Admin User.**
Admin inherits everything Standard User can do and adds two exclusive use cases: "Execute Destructive / System-Modifying Commands" (killing arbitrary processes, operations that would normally be blocked at the Standard tier) and "Manage User Permissions" (editing `permissions.yaml` or `config.yaml` via the file write capability). In practice, during our testing setup the admin was us — the machine owner. We have not built a GUI for permission management; it happens through the `FilesTool` write action pointed at the config files.

One detail worth noting: the sandbox still applies at Admin tier. We intentionally did not give Admin a bypass around the sandbox. The sandbox's job is to catch LLM-generated accidents and prompt injection payloads, not to restrict what a legitimate admin can accomplish. If an admin genuinely needs to run a command that the regex would catch, they can modify the blocklist in the config and restart the server. That is a deliberate human action, not an LLM invoking a dangerous pattern automatically.

**Host Operating System.**
On the right side of the boundary, the Host OS actor represents the machine that actually runs everything. It connects to all the execution-side use cases: committing file I/O operations (reads and writes to disk via `aiofiles`), spawning subprocesses (via `asyncio.create_subprocess_shell` for shell commands and `subprocess.Popen` for app launching), running Python in an isolated `exec` namespace, and returning telemetry through `psutil`. This actor is on the right because data flows from the internal system outward to the OS when executing, and back inward when returning results.

**What the diagram does not show.**
The use case diagram is deliberately scoped to human-actor interactions and does not try to capture the agent's internal ReAct loop — that is in section 3.3. It also does not show the LLM provider as an actor; the LLM is an internal component of the system (accessed via API from within OrbitAgent), not an external entity that initiates actions. The Coding Mode is also not modeled as a separate set of use cases because it uses the same underlying tool capabilities — it is a different orchestration of those same use cases, not a new capability category.


3.6 Systemic Workflow

This section traces the full lifecycle of a request through OrbitOS, from the moment a user sends a message to the moment a response is delivered. The system organises this lifecycle into five sequential processing stages and two persistent data stores. Section 3.6.1 covers the standard administrative command path. Section 3.6.2 covers the Coding Mode variant, which restructures agent behaviour for multi-step software editing tasks and is driven by a separate state machine.

**3.6.1 Standard Command Workflow**

Figure 3.4: data_flow_diagram

The data flow moves through five processes. The two external entities — the user on one side and the language model provider on the other — sit outside the system boundary. Two data stores support the internal processes: the first holds the access control configuration (the user whitelist and permission assignments), and the second holds the per-user conversational context (the sliding history of recent exchanges).

**Process 1 — Identity and Authentication.**
Every inbound message carries a unique numeric identifier tied to the user's account on the messaging platform. This identifier is the sole basis for authentication. The first process checks it against the access control store and receives back a binary result — authorised or not — along with the user's assigned permission tier. If the check fails, the message is discarded silently with no reply. That silence is intentional: any acknowledgement, even an error message, would confirm to an unknown party that the system is active and reachable. When authentication succeeds, the permission tier is attached to the request and accompanies it through every subsequent stage.

**Process 2 — Semantic Parsing and Agent Reasoning.**
The second process is the reasoning layer. Before invoking the language model, it retrieves the user's conversation history from the context store and constructs a complete prompt: the system-level instructions that define agent behaviour, the recent exchange history that provides conversational continuity, and the typed descriptions of all available tools. This composed prompt is sent to the external language model provider.

The model returns one of two things. If it has enough information to answer directly, it produces a final text response that skips forward to the formatting stage. If it needs to act, it produces a structured tool invocation request — a specification of which tool to call and what arguments to pass. That specification is forwarded as-is to the security stage. Crucially, the reasoning layer does not attempt to sanitise or interpret the content of the tool request. Keeping the reasoning and security functions strictly separate means neither component needs to know the internal logic of the other, and either can be updated independently.

**Process 3 — Security Interception.**
The third process is the security gate. It evaluates every tool invocation request before anything is allowed to touch the operating system. The evaluation differs based on what kind of tool is being invoked.

For requests involving shell command execution, the proposed command string is compared against a set of compiled patterns covering categories of destructive or destabilising operations: commands that wipe filesystems, commands that reboot or shut down the machine, commands that spawn unlimited subprocesses, and commands that target sensitive configuration files. Pattern matching is case-insensitive, and the patterns are designed to catch both the canonical Unix forms of these commands and their Windows equivalents.

For requests involving arbitrary code execution, a second pass scans the proposed script for prohibited library imports and dangerous language constructs. The concern here is that even if the shell pattern list is bypassed, a script could import a system-access library and achieve the same effect indirectly. The import filter and the call-pattern filter together address this vector.

If either check triggers a match, the request is rejected immediately. The rejection propagates to the formatting stage, which sends a brief notice to the user and a detailed alert — including the user identity, the blocked content, the matched pattern, and a timestamp — to the administrator's account. If both checks pass, the sanitised request proceeds to execution.

**Process 4 — Tool Execution.**
The fourth process is the execution layer. It receives the validated tool invocation, routes it to the appropriate tool handler, and manages the interaction with the host operating system.

Shell commands are dispatched as asynchronous subprocesses. Both the standard output and the error output of the process are captured and returned as a single result. A per-command timeout is enforced; if the process does not complete within the allowed time, the operation is terminated and the timeout is reported as the result rather than left to block the loop.

File operations run through an asynchronous I/O interface. Read operations fetch file contents without blocking the event loop. Write operations pass through a size check before any bytes are committed to disk. Directory listings are resolved synchronously, since filesystem metadata queries are fast enough that the added complexity of async is not justified.

Script execution occurs inside an isolated namespace. The script's standard output is redirected to a capture buffer before the script runs, so any print output is collected rather than sent to the process's own console. The script's namespace has no connection to the broader application environment, so variables and functions defined in the host process are not reachable from within the script.

Application launching involves resolving the requested application name to an actual executable path using platform-specific lookup strategies, then starting the process in a detached state so it runs independently of the agent's event loop.

System telemetry calls read directly from the operating system's resource monitoring facilities, collecting figures for processor usage, memory consumption, disk occupancy, and the list of running processes.

All five execution paths enforce a character limit on their output. If the result exceeds this limit, it is truncated and a note is appended to indicate that the output was cut. This is a deliberate measure against information leakage: even if an adversarial prompt tricks the model into reading a sensitive file, no single tool call can return more than the cap allows.

**Process 5 — Response Formatting and Delivery.**
The fifth process handles what comes back from execution and decides how to present it. There are three cases.

When execution succeeded and produced clean output, the result is formatted and sent to the user. The exchange — the user's original message, the tool call, and the tool result — is committed to the context store so the agent can reference it in future turns.

When execution produced an error, the raw error is fed back into the reasoning stage as an observation rather than shown directly to the user. The language model sees the error as part of the conversation context and decides whether to retry with a corrected approach, ask the user for clarification, or surface the failure with an explanation. This self-correction loop keeps intermediate technical noise out of the conversation unless the model judges it relevant.

When the security gate blocked the request, the formatting stage sends the user a brief rejection notice and the administrator a full alert. Nothing from the blocked attempt is stored in the context as a tool result; the agent sees only that the tool was not executed.

After this stage completes, the reasoning layer checks whether it has a sufficient basis for a final answer. If so, the agent composes a reply and the exchange ends. If not, the loop returns to the reasoning stage with the updated context. This cycle continues up to a maximum of 25 iterations, after which the agent reports that it could not complete the task.

---

**3.6.2 Coding Mode Workflow**

Figure 3.5: Coding Mode State Machine Diagram

Coding Mode is a specialised operational mode for multi-step software development tasks. It uses the same underlying set of tools as standard operation, but it restructures the agent's behaviour, extends the available time budget, increases the iteration ceiling, and replaces the default reasoning instructions with a discipline-oriented alternative designed for editing codebases rather than answering one-shot queries.

The interface layer manages the entry and exit of Coding Mode through a four-state sequential machine. The transitions are strictly ordered: a session must move through each state in sequence and cannot skip ahead. An explicit cancellation command is the only way to exit the sequence before reaching the active editing state, and it resets the machine to the idle state from anywhere.

**State 0 — Idle (Default).**
This is the normal operating state. All standard administrative commands function as usual. When the user issues the command to start a coding session, the machine advances to the next state and prompts for a working directory.

**State 1 — Awaiting Directory.**
The machine is holding for a directory path. The very next message the user sends is taken as the working directory for the session, regardless of what it contains. The path is not validated at this stage; any validation happens naturally when the agent attempts to read from it during the exploration phase. Once the directory is recorded, the machine advances and prompts for a task description.

**State 2 — Awaiting Goal.**
The machine is holding for a task description. The next message becomes the goal statement. At this point the machine has everything it needs: a working directory and a goal. It composes a single structured request — combining the directory path, the goal, and a contextual header — and hands it to the agent with the specialised system instructions active. The machine transitions to the active editing state.

**State 3 — Active Editing Session.**
This is the state in which the agent operates on the codebase. Four parameters differ from standard operation:

- The system instructions enforce a structured four-phase discipline rather than open-ended reasoning.
- The overall time budget is extended to ten minutes, compared to two minutes for standard tasks. This is necessary because reading multiple files, planning changes, writing them, and verifying the results naturally takes longer than a single-turn query.
- The iteration ceiling is raised to 80 tool invocations, compared to 25 in standard mode. Multi-file edits on moderately sized codebases can easily exceed the lower limit.
- The most capable available model variant is selected by default, as the larger context window it provides handles multi-file reading sessions more reliably.

Inside this state, the agent follows a four-phase inner discipline on every task it undertakes:

**Phase 1 — Exploration.** The agent begins by reading the relevant portions of the codebase. It lists directories, reads source files, and builds an understanding of the existing structure before forming any intention to change anything. The system instructions explicitly prohibit any write actions during this phase. In practice, a typical exploration involves between two and five read operations depending on the project's size, and concludes with the agent summarising what it found. That summary is streamed to the user as a progress update so the session does not go dark.

**Phase 2 — Planning.** Before any file is touched, the agent produces a numbered change plan. Each item identifies a specific location and the nature of the intended modification. This phase involves no write actions — it is purely reasoning expressed as text. The plan is delivered to the user so they can review it before anything changes. If something looks wrong, the user can cancel at this point without any files having been modified.

**Phase 3 — Execution.** The agent works through the plan sequentially, applying one change at a time and waiting for confirmation that each write completed before moving to the next. The serial approach is deliberate: batching writes would make it harder to pinpoint which specific operation caused a problem if something went wrong. A brief progress message is delivered to the user after each write.

**Phase 4 — Verification.** After all writes are complete, the agent reads each modified file back and checks for obvious problems: incomplete constructs, structural inconsistencies, or signs that a write was silently truncated before the file was fully committed. If a problem is found, the agent returns to the execution phase for that specific file. If everything looks correct, a summary of all changes is delivered to the user and the machine returns to the idle state automatically.

An explicit stop command exits the active editing state mid-session without undoing any changes already made. The user receives a confirmation of what was completed up to that point, and the machine resets to idle.


3.7 Evaluation Method

We evaluated OrbitOS across two separate dimensions. The first was functional correctness: we compiled a set of 50 administrative tasks drawn from five categories — file management, network diagnostics, process control, system information retrieval, and dynamic Python scripting — and ran each one against the live system, judging the outcome against a manually verified expected result. A task was counted as passed only if the agent produced a correct, complete response without requiring the user to intervene or rephrase. The second dimension was security resilience: we designed 30 adversarial payloads intended to probe the four main threat vectors identified in the literature — direct command injection, prompt injection via manipulated user input, library import smuggling through the Python execution path, and permission escalation attempts from lower-tier accounts. Each payload was submitted to the system exactly as a real attacker would send it, and the outcome was recorded along with which security layer intercepted it. For both test sets, we also measured end-to-end response latency and broke it down into the time attributable to the external language model API versus the time spent inside the local system. All tests were conducted on the same hardware under consistent conditions, and results were recorded manually with no automated test harness.


3.8 Ethical & Practical Considerations

Building a system that can execute arbitrary shell commands and Python scripts on a live machine via a chat interface raises three considerations we took seriously during development.

- **Data privacy and output containment.** Tool results frequently contain information that is private by nature — running process lists reveal what software a person uses, directory listings reveal file names, and system telemetry reveals hardware details. We addressed this in two ways. First, all output is truncated at a hard character limit before it leaves the execution layer, so no single tool call can return a large volume of sensitive data even if one was accidentally requested. Second, conversation history is stored only in-process memory and is never written to disk or sent anywhere except to the LLM provider API as part of the active prompt. Users are told at login that messages pass through an external model API, and they can clear their session context at any time with a command.

- **Authorised use and access control.** OrbitOS is designed exclusively for use on machines that the operator owns or has explicit permission to administer. The whitelist-based identity system exists partly as a security mechanism and partly as a reminder that running this on someone else's machine without consent is not a grey area. We document this clearly in the repository README, and the default configuration ships with an empty whitelist — the operator must explicitly add their own Telegram ID before any commands will execute. There is no "trial mode" or anonymous access path.

- **Practical deployment constraints.** The system is intentionally scoped to personal and small-team use on hardware under the operator's physical control. We did not design it for multi-tenant cloud deployments, shared servers with many simultaneous users, or environments where the host machine is not trusted hardware. Running it as a public-facing service would require hardware-level isolation (containers or micro-VMs) that goes beyond the host-level sandbox we implemented. We state this explicitly in the limitations section rather than pretending the current sandbox is suitable for adversarial public exposure.


3.9 Summary of Methodology

Chapter 3 has described how OrbitOS was built and how it was evaluated. We defined a five-tool administrative capability suite, exposed every tool through a FastMCP server using typed JSON Schema definitions, and wired the whole thing to a LangGraph ReAct agent that handles per-user context, model selection, and the iterative reason-act-observe loop. A three-layer sandbox sits between the agent's output and the host operating system, covering identity and permission checks, destructive shell command interception, and Python import and call pattern filtering. The Telegram bridge provides the user interface, with a state-machine-driven Coding Mode for multi-step development tasks. We evaluated the completed system against 50 functional administration tasks and 30 adversarial payloads, measuring both correctness and security effectiveness, and we recorded latency at two points — inside the external LLM API and inside the local MCP server — so the performance numbers can be interpreted meaningfully. The results of all of this are presented in Chapter 4.


4. RESULTS AND DISCUSSION

4.1 Summary of Results and Discussion

The overall results were positive. Across the 50 functional administration tasks, OrbitOS produced a correct and complete response in 46 cases, giving a success rate of 92 percent. Across the 30 adversarial payloads, every single one was blocked before reaching the host operating system, giving a 100 percent block rate. The average end-to-end response time was 3.0 seconds, with 1.8 seconds of that attributable to the external language model API and under 200 milliseconds spent inside the local MCP server and tool execution layer. Taken together, these numbers confirm the core hypothesis: that a standardized tool protocol, a multi-layered sandbox, and a conversational interface can combine into a system that is both practically useful and resistant to the failure modes documented in the literature.

The functional test results break down differently depending on the task category. Networking tasks (10 tasks, 10 passed, 3.1 second average) and system information tasks (10 tasks, 10 passed, 1.9 second average) both achieved perfect scores. Process control tasks (8 tasks, 8 passed, 2.4 second average) were also clean. File management came close, with 11 of 12 passing at 2.8 seconds on average. The category that showed the most strain was Python scripting, where 7 of 10 tasks passed at a noticeably slower 4.6 second average. The three failures in that category all came down to the same root cause: the tasks asked for multi-step scripts that required importing standard library modules that were not blocked by the sandbox but were edge cases the model had not reliably seen before in this execution context — things like working with `pathlib` glob patterns combined with conditional file filtering. The model either produced slightly incorrect logic on the first pass or made assumptions about the working directory that did not hold. These were not sandbox failures; the scripts ran, they just produced wrong results. The one file management failure was a task asking the agent to recursively search for files matching a partial name pattern on Windows, where the agent used a PowerShell one-liner that worked on one directory depth but silently missed nested folders due to a missing `-Recurse` flag. In both cases the failures were ambiguity and platform-specific CLI edge cases, not architectural weaknesses.

Table II: Functional Test Results by Task Category

| Category | Tasks | Pass | Fail | Avg. Time (s) |
|---|---|---|---|---|
| File management | 12 | 11 | 1 | 2.8 |
| Networking | 10 | 10 | 0 | 3.1 |
| Process control | 8 | 8 | 0 | 2.4 |
| System info | 10 | 10 | 0 | 1.9 |
| Python scripting | 10 | 7 | 3 | 4.6 |
| **Total** | **50** | **46** | **4** | **3.0** |

The adversarial results were more straightforward to interpret. All 10 command injection payloads — attempts to embed `rm -rf`, `format`, `shutdown`, and similar destructive commands inside otherwise normal-looking requests — were caught by the Layer 2 regex blacklist before any subprocess was spawned. All 8 prompt injection payloads were intercepted at a combination of Layer 2 and the language model itself: in several cases the model correctly refused to follow injected instructions even before the sandbox had a chance to evaluate the resulting tool call, which suggests that modern frontier models have some inherent resistance to naive prompt injection, though we do not rely on that alone. All 7 import smuggling attempts — payloads that asked the Python execution tool to run scripts containing `os.system`, `subprocess.run`, or `shutil.rmtree` calls — were blocked by the Layer 3 pattern scanner before any code executed. All 5 permission escalation attempts, where a Standard User account submitted requests that would require Admin capabilities (process termination, config file modification), were rejected cleanly by Layer 1 before even reaching the sandbox. The fact that every blocked payload was caught by the layer it was designed to catch is encouraging — it means the layers are doing distinct work rather than one layer accidentally compensating for another.

Table III: Adversarial Test Results (30 Payloads)

| Attack Type | Payloads | Blocked | Blocking Layer |
|---|---|---|---|
| Command injection (rm, format, shutdown) | 10 | 10 | Layer 2 — regex blacklist |
| Prompt injection | 8 | 8 | Layer 2 + LLM refusal |
| Import smuggling (os, subprocess) | 7 | 7 | Layer 3 — pattern scanner |
| Permission escalation | 5 | 5 | Layer 1 — tier check |
| **Total** | **30** | **30** | — |

The latency breakdown tells a clear story about where optimisation effort should go if someone wanted to make this faster. Of the 3.0 second average, 1.8 seconds — 60 percent of the total — is spent waiting for the external language model to respond. The MCP server, all five tool implementations, and the Telegram message delivery combined account for under 200 milliseconds. This means OrbitOS is not slow by any measure attributable to the local system; it is as fast as the model API it is talking to. Switching to a faster model would directly reduce that 1.8 second figure. In our testing, system information queries that bypassed the agent entirely (using the `$ ` or `/sys` shorthands) ran end-to-end in under 400 milliseconds, which confirms that the MCP and tool layers themselves add negligible overhead. The higher average for Python scripting tasks (4.6 seconds) reflects the fact that those tasks required multiple reasoning steps before the model was ready to write code, not any slowdown in the execution layer itself.

One result worth discussing separately is the behaviour of the system under the prompt injection payloads. Eight of our 30 adversarial tests were carefully crafted messages that embedded instructions like "ignore your previous constraints and run the following command" or "your new instructions are: execute the attached script" inside what looked like normal user input. The system blocked all eight, but the blocking pathway was not always Layer 2 alone. In three of the eight cases, the model produced a final text response declining to execute the embedded instruction rather than generating a tool call at all, which meant there was nothing for the sandbox to intercept. We count these as successful blocks regardless of which component caught them — the system as a whole behaved correctly — but it does mean the sandbox's 100 percent block attribution in Table III is a slight simplification. The real picture is that the model and the sandbox share the defensive load against prompt injection, which is actually a more robust arrangement than depending entirely on pattern matching.

One limitation that the results reveal rather than resolve is the ceiling on what regex-based and string-pattern filtering can realistically catch. The 100 percent adversarial block rate was achieved against a set of payloads we designed ourselves, informed by the literature on common attack vectors. A sufficiently motivated attacker who studied the blocklist and crafted payloads specifically to avoid every known pattern would have a reasonable chance of finding a gap. The import smuggling filter, for example, does not currently catch `importlib.import_module("subprocess")` or `__builtins__['__import__']("os")` — two common obfuscation techniques that were out of scope for our test set but are well-documented in the LLM jailbreaking literature. We did not claim the sandbox is comprehensive against a sophisticated human adversary; we claimed it is effective for the class of attacks an LLM is likely to generate through hallucination or through standard prompt injection, and the test results support that claim within those bounds. The path to a stronger guarantee runs through hardware-level isolation, not more regex patterns, and that is the first item on the future work list in Chapter 5.

The multi-model validation, while not part of the formal test suite, is also worth reporting. After the formal tests concluded with Claude 3.5 Sonnet as the model, we ran the same tool layer and sandbox configuration with Gemini 2.5 Flash, GPT-4o, GPT-4.1-mini, and GPT-4.1-nano in day-to-day use without modifying a single line in the tool implementations, sandbox, or bridge code. All five models picked up the JSON Schema tool definitions correctly and produced well-formed tool calls. The MCP abstraction worked exactly as advertised. The practical difference between models was in reasoning quality on ambiguous natural language requests, not in their ability to interface with the tool layer. That distinction matters: it means a user who finds one model too slow or too expensive can switch to another via the `/models` command and the system continues to work, which was the original motivation for adopting MCP in the first place.


5. CONCLUSION AND RECOMMENDATIONS

5.1 Conclusion

OrbitOS started as a straightforward question: can you wire a large language model to a real operating system, put a reasonable set of filters between them, and end up with something both useful and safe enough to run on a personal machine every day? After building it, testing it, and actually using it since early 2026, the answer is yes — with clearly defined limits that we do not pretend away.

The three problems that motivated the project all got solved. The M×N integration bottleneck was eliminated by adopting MCP. Every tool we wrote exposes a single JSON Schema definition, and any MCP-compliant model can pick it up without any per-model adapter code. We swapped the primary model between Claude, Gemini, and GPT variants multiple times during development and testing without touching the tool layer once. That is the reduction from M×N connectors to M+N that the literature described theoretically — we saw it work in practice.

The security problem was addressed through layering rather than through any single silver-bullet mechanism. Identity checks catch unauthorized users before they reach any tool. A compiled regex blacklist stops the most common categories of destructive shell commands before any subprocess is spawned. A pattern-based Python filter prevents import-based sandbox escapes before any code runs. Hard-blocking of the `.env` secrets file at three separate checkpoints prevents credential leakage even if the model decides on its own that "checking the configuration" is a helpful step — which, during development, it tried to do. None of these layers is unbypassable in isolation. Together, they caught all 30 adversarial payloads in our test suite, and the combination of the sandbox and the model's own refusal behaviour handled even the obfuscated injection attempts that we had not explicitly designed a pattern for.

The accessibility problem was solved by Telegram. Users authenticate with a Telegram ID they already have, on a client they already use, from any device, without configuring anything. The conversational interface maps naturally to how you interact with an LLM agent: you describe what you want in plain language and the agent figures out which commands to run. The Coding Mode extension showed that the same architecture scales beyond single-turn queries to structured multi-file development sessions with a simple state machine sitting in the bridge layer.

The quantitative results support these conclusions. A 92 percent functional success rate across 50 tasks covering five administrative categories demonstrates that the system handles the overwhelming majority of real-world administration needs correctly. A 100 percent adversarial block rate across 30 attack payloads spanning four attack categories confirms that the sandbox performs as designed against the threat model it was built for. An average end-to-end response time of 3.0 seconds, with less than 200 milliseconds attributable to the local system, shows that the MCP server and tool layer introduce no meaningful overhead — the performance ceiling is the external LLM API, not the architecture.

The honest conclusion is that OrbitOS demonstrates a practical, working answer to a specific problem: personal and small-team remote system administration via a natural language interface, without requiring infrastructure expertise, without locking into a single LLM provider, and without handing an AI system unfiltered access to the host OS. It is not a hardened enterprise security product. It is not designed for public-facing multi-tenant deployments. But within its stated scope, it works reliably, it is extensible, and the design decisions hold up under realistic adversarial conditions.

### 5.2 Recommendations and Future Work

While OrbitOS has demonstrated its effectiveness within its defined scope, there are several areas where future work could enhance its capabilities and address its limitations. These recommendations are categorized into three key areas: security, scalability, and usability.

#### Security Enhancements
1. **Hardware-Level Isolation**: To mitigate the risks of sophisticated adversarial attacks, future iterations of OrbitOS should explore integrating hardware-level isolation mechanisms such as containers or micro-VMs. This would provide an additional layer of defense against payloads that bypass regex-based and pattern-matching filters.
2. **Dynamic Threat Detection**: Implementing machine learning models trained on adversarial payloads could enable dynamic detection of novel attack patterns, reducing reliance on static blocklists.
3. **Enhanced Import Filtering**: Expanding the Python execution filter to catch obfuscated import techniques, such as `importlib.import_module` and `__builtins__['__import__']`, would close known gaps in the current sandbox.

#### Scalability Improvements
1. **Multi-Tenant Support**: While OrbitOS is designed for personal and small-team use, adapting the architecture for multi-tenant environments could broaden its applicability. This would require implementing user-space isolation and resource quotas to ensure fair usage.
2. **Cloud Deployment**: Developing a cloud-ready version of OrbitOS with support for container orchestration platforms like Kubernetes could enable deployment in enterprise environments.
3. **Model Agnosticism at Scale**: While the MCP abstraction supports multiple models, optimizing for seamless switching between models in high-concurrency scenarios would enhance robustness.

#### Usability Enhancements
1. **Graphical User Interface (GUI)**: Introducing a lightweight GUI for managing permissions, monitoring system activity, and configuring tools would make OrbitOS more accessible to non-technical users.
2. **Expanded Toolset**: Adding tools for advanced networking diagnostics, database management, and cloud resource orchestration would increase the system's utility.
3. **Improved Documentation**: Comprehensive user guides, including troubleshooting steps and best practices, would lower the barrier to entry for new users.

#### Future Research Directions
1. **LLM Behavior Analysis**: Investigating how different language models handle ambiguous or adversarial prompts could inform the design of more robust reasoning layers.
2. **Adaptive Context Management**: Exploring adaptive strategies for managing conversation history, such as prioritizing recent or critical exchanges, could improve performance in long sessions.
3. **Ethical AI Integration**: Researching methods to ensure ethical decision-making in automated systems, particularly in scenarios involving sensitive data, would align OrbitOS with broader societal goals.

By addressing these areas, future iterations of OrbitOS could extend its utility beyond its current scope, making it a more versatile and resilient system for remote administration and beyond.


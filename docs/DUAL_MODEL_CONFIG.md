# Dual-Model Configuration Guide

## Quick Start

### 1. Start Ollama (for local models)

```bash
ollama serve
```

### 2. Check Available Configurations

```bash
openlaoke
/dual-config
```

Output:
```
Dual-Model Configuration

Active: local_balanced

Available Configurations:
┌─────────────────┬─────────────────────────┬──────────────────────────┬─────────┐
│ Name            │ Planner                 │ Executor                 │ Type    │
├─────────────────┼─────────────────────────┼──────────────────────────┼─────────┤
│ local_balanced  │ gemma3:1b (ollama)      │ gemma4:e4b (ollama)      │ local   │
│ local_light     │ gemma3:1b (ollama)      │ gemma4:e2b (ollama)      │ local   │
│ hybrid_openai   │ gemma3:1b (ollama)      │ gpt-4-turbo (openai)     │ hybrid  │
│ hybrid_anthropic│ gemma3:1b (ollama)      │ claude-3-opus (anthropic)│ hybrid  │
│ online_premium  │ gpt-3.5-turbo (openai)  │ claude-3-opus (anthropic)│ online  │
└─────────────────┴─────────────────────────┴──────────────────────────┴─────────┘
```

### 3. Select a Configuration

```bash
/dual-config use hybrid_openai
```

### 4. Use Dual-Model Workflow

```bash
/dual write a Python program to calculate disk storage
```

---

## Configuration Types

### 1. Local + Local (Recommended for privacy)

**Use when:**
- You have good GPU (12+ GB VRAM)
- Privacy is important
- No internet access needed

**Configuration:**
```
Planner:   gemma3:1b (Ollama, CPU)
Executor:  gemma4:e4b (Ollama, GPU)
Validator: gemma3:1b (Ollama, CPU)

Cost: Free (local)
Quality: 8.5/10
Speed: Fast (no network)
```

**Setup:**
```bash
# 1. Start Ollama
ollama serve

# 2. Pull models
ollama pull gemma3:1b
ollama pull gemma4:e4b

# 3. Use in OpenLaoKe
/dual-config use local_balanced
```

---

### 2. Local + Online (Best cost/quality balance)

**Use when:**
- Simple planning (local model is enough)
- Need powerful execution (online model)
- Want to save costs

**Configuration:**
```
Planner:   gemma3:1b (Ollama, CPU) - Free
Executor:  gpt-4-turbo (OpenAI) - $0.01/1K tokens
Validator: gemma3:1b (Ollama, CPU) - Free

Cost: ~$0.10 per complex task
Quality: 9.0/10
Speed: Medium (network latency for executor)
```

**Setup:**
```bash
# 1. Set OpenAI API key
export OPENAI_API_KEY="sk-xxx"

# 2. Start Ollama
ollama serve

# 3. Pull local model
ollama pull gemma3:1b

# 4. Use hybrid config
/dual-config use hybrid_openai
```

---

### 3. Online + Online (Maximum quality)

**Use when:**
- Need highest quality
- Complex tasks
- No local resources

**Configuration:**
```
Planner:   gpt-3.5-turbo (OpenAI) - $0.0005/1K tokens
Executor:  claude-3-opus (Anthropic) - $0.015/1K tokens
Validator: gpt-3.5-turbo (OpenAI) - $0.0005/1K tokens

Cost: ~$0.50 per complex task
Quality: 10.0/10
Speed: Medium (network for all)
```

**Setup:**
```bash
# 1. Set API keys
export OPENAI_API_KEY="sk-xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"

# 2. Use online config
/dual-config use online_premium
```

---

## Custom Configurations

### Create a Custom Config

```bash
/dual-config create my_config \
  planner=ollama:gemma3:1b \
  executor=openai:gpt-4 \
  executor-key=sk-xxx
```

### Full Options

```bash
/dual-config create custom \
  planner=ollama:gemma3:1b \
  executor=anthropic:claude-3-opus \
  validator=openai:gpt-3.5-turbo \
  planner-key=sk-xxx \
  executor-key=sk-ant-xxx \
  validator-key=sk-yyy
```

---

## Provider Setup

### Ollama (Local)

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Start
ollama serve

# Pull models
ollama pull gemma3:1b
ollama pull gemma4:e4b

# Check
ollama list
```

### OpenAI

```bash
# Get API key from https://platform.openai.com/api-keys
export OPENAI_API_KEY="sk-xxx"

# Available models
# - gpt-3.5-turbo (fast, cheap)
# - gpt-4-turbo (balanced)
# - gpt-4o (latest)
```

### Anthropic

```bash
# Get API key from https://console.anthropic.com/
export ANTHROPIC_API_KEY="sk-ant-xxx"

# Available models
# - claude-3-haiku (fast)
# - claude-3-sonnet (balanced)
# - claude-3-opus (best quality)
```

### Google Gemini

```bash
# Get API key from https://makersuite.google.com/app/apikey
export GOOGLE_API_KEY="xxx"

# Available models
# - gemini-pro
# - gemini-1.5-pro
```

### DeepSeek

```bash
# Get API key from https://platform.deepseek.com/
export DEEPSEEK_API_KEY="xxx"

# Available models
# - deepseek-chat
# - deepseek-coder
```

---

## Commands Reference

### `/dual-config`

Show all configurations and active config.

### `/dual-config list`

List all available configuration names.

### `/dual-config use <name>`

Select active configuration.

Example:
```bash
/dual-config use hybrid_openai
```

### `/dual-config check`

Check availability of all models in active config.

Output:
```
Model Availability
┌───────────┬────────────────────────┬──────────────┬─────────────────────┐
│ Role      │ Model                  │ Status       │ Message             │
├───────────┼────────────────────────┼──────────────┼─────────────────────┤
│ planner   │ gemma3:1b (ollama)     │ ✓ Available  │ Ollama is running   │
│ executor  │ gpt-4-turbo (openai)   │ ✓ Available  │ openai configured   │
│ validator │ gemma3:1b (ollama)     │ ✓ Available  │ Ollama is running   │
└───────────┴────────────────────────┴──────────────┴─────────────────────┘
```

### `/dual-config create <name> <options>`

Create custom configuration.

Options:
- `planner=<provider>:<model>` - Planner model
- `executor=<provider>:<model>` - Executor model
- `validator=<provider>:<model>` - Validator model (optional)
- `planner-key=<api_key>` - API key for planner (optional)
- `executor-key=<api_key>` - API key for executor (optional)
- `validator-key=<api_key>` - API key for validator (optional)

---

## Troubleshooting

### Ollama Connection Failed

**Error:**
```
Dual-model execution failed: All connection attempts failed
```

**Solution:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama
ollama serve

# Or use online models instead
/dual-config use online_premium
```

### Missing API Key

**Error:**
```
openai requires API key
```

**Solution:**
```bash
# Set API key
export OPENAI_API_KEY="sk-xxx"

# Or provide in command
/dual-config create my_config \
  planner=ollama:gemma3:1b \
  executor=openai:gpt-4 \
  executor-key=sk-xxx
```

### Out of VRAM

**Error:**
```
GPU out of memory
```

**Solution:**
```bash
# Use lighter models
/dual-config use local_light

# Or use online models
/dual-config use hybrid_openai
```

---

## Examples

### Example 1: Simple Python Script (Local)

```bash
# Use local models (free)
/dual-config use local_balanced

# Generate code
/dual write a Python script to list all files in a directory
```

### Example 2: Complex System (Hybrid)

```bash
# Use hybrid (cheap planner, powerful executor)
/dual-config use hybrid_openai

# Generate complex system
/dual write a REST API with authentication, database, and caching
```

### Example 3: Critical Production Code (Premium)

```bash
# Use best models
/dual-config use online_premium

# Generate production code
/dual write a payment processing system with PCI compliance
```

---

## Cost Comparison

| Configuration | Cost per Task | Quality | Speed |
|--------------|--------------|---------|-------|
| local_balanced | $0.00 | 8.5/10 | Fast |
| local_light | $0.00 | 7.0/10 | Fast |
| hybrid_openai | ~$0.10 | 9.0/10 | Medium |
| hybrid_anthropic | ~$0.20 | 9.5/10 | Medium |
| online_premium | ~$0.50 | 10.0/10 | Medium |

---

## Advanced: Programmatic Usage

```python
from openlaoke.core.dual_model_config import create_config_manager

# Create manager
manager = create_config_manager()

# Create custom config
manager.create_custom_config(
    name="my_custom",
    planner_provider="ollama",
    planner_model="gemma3:1b",
    executor_provider="openai",
    executor_model="gpt-4-turbo",
    executor_api_key="sk-xxx",
)

# Set active
manager.set_active_config("my_custom")

# Get config
config = manager.get_config()
print(f"Planner: {config.planner.model_name}")
print(f"Executor: {config.executor.model_name}")
```

---

## File Locations

- Configurations: `~/.openlaoke/dual_model_configs/configs.json`
- Logs: `~/.openlaoke/logs/`

---

## Related Commands

- `/dual` - Execute with dual-model workflow
- `/preload-models` - Preload local models
- `/model-status` - Check model pool status
- `/model-recommend` - Get optimal models for your system
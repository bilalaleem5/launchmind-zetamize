"""
===============================================================
  AI SALES SYSTEM — MCP Registry
  Foundation for AI tools and external service connectors.
===============================================================
"""

class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, description, func):
        self.tools[name] = {
            "description": description,
            "func": func
        }
        print(f"🔧 Tool Registered: {name}")

    def get_tool_definitions(self):
        return {name: info["description"] for name, info in self.tools.items()}

    def execute_tool(self, tool_name, **kwargs):
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")
        return self.tools[tool_name]["func"](**kwargs)

# Global registry
mcp_registry = ToolRegistry()

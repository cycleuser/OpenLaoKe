"""Example demonstrating the long-term memory and knowledge graph system."""

from __future__ import annotations

import asyncio

from openlaoke.core.memory import (
    KnowledgeGraph,
    KnowledgeNode,
    LongTermMemory,
    Memory,
)


async def main() -> None:
    print("=== Long-Term Memory System Demo ===\n")

    ltm = LongTermMemory()

    print("1. Storing memories...")
    m1 = Memory(id="", content="Python is a programming language created by Guido van Rossum")
    m2 = Memory(id="", content="JavaScript is used for web development")
    m3 = Memory(id="", content="Machine learning uses Python extensively")

    id1 = await ltm.store(m1)
    id2 = await ltm.store(m2)
    id3 = await ltm.store(m3)

    print(f"   Stored memory 1: {id1}")
    print(f"   Stored memory 2: {id2}")
    print(f"   Stored memory 3: {id3}\n")

    print("2. Recalling memories about Python...")
    results = await ltm.recall("Python programming", limit=2)
    for i, memory in enumerate(results):
        print(f"   {i + 1}. {memory.content} (importance: {memory.importance:.2f})\n")

    print("3. Creating associations...")
    await ltm.associate([id1, id3])
    print(f"   Associated {id1} and {id3}\n")

    print("4. Memory summary...")
    summary = await ltm.summarize()
    print(f"   Total memories: {summary.total_memories}")
    print(f"   Total associations: {summary.total_associations}")
    print(f"   Average importance: {summary.avg_importance:.2f}\n")

    print("=== Knowledge Graph Demo ===\n")

    kg = KnowledgeGraph()

    print("5. Building knowledge graph...")
    python_node = KnowledgeNode(id="", type="language", content="Python")
    ml_node = KnowledgeNode(id="", type="field", content="Machine Learning")
    lib_node = KnowledgeNode(id="", type="library", content="TensorFlow")

    python_id = await kg.add_node(python_node)
    ml_id = await kg.add_node(ml_node)
    lib_id = await kg.add_node(lib_node)

    await kg.add_edge(python_id, ml_id, "used_in")
    await kg.add_edge(ml_id, lib_id, "uses")

    print(f"   Added nodes: {python_id}, {ml_id}, {lib_id}")
    print("   Added edges: Python -> ML, ML -> TensorFlow\n")

    print("6. Finding neighbors...")
    neighbors = kg.get_neighbors(python_id)
    print(f"   Neighbors of Python: {[n.content for n in neighbors]}\n")

    print("7. Finding path...")
    path = kg.find_path(python_id, lib_id)
    if path:
        path_content = [kg.nodes[n].content for n in path]
        print(f"   Path from Python to TensorFlow: {path_content}\n")

    print("8. Knowledge graph visualization...")
    viz = await kg.visualize()
    print(f"   Nodes: {len(viz.nodes)}")
    print(f"   Edges: {len(viz.edges)}\n")

    print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

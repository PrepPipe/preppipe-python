# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
import collections
import os
import tempfile
import graphviz
from ..irbase import IList, IListNode, get_sanitized_filename
from ..language import TranslationDomain

# ----------------------------------------------------------
# 图本身的类
# ----------------------------------------------------------

class GenericNodeBase(IListNode):
  _incomingedges : IList
  _outgoingedges : IList

  def get_node_label(self) -> str:
    return self.__class__.__name__ + ' ' + hex(id(self))
  def get_node_description(self) -> typing.Iterable[str] | None:
    return None

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._incomingedges = IList(self)
    self._outgoingedges = IList(self)

  def get_incoming_edges(self) -> typing.Iterable[GenericEdgeBase]:
    return self._incomingedges
  def get_outgoing_edges(self) -> typing.Iterable[GenericEdgeBase]:
    return self._outgoingedges

  def __str__(self) -> str:
    result = self.get_node_label()
    if details := self.get_node_description():
      result += '\n  ' + '\n  '.join(details)
    in_edge_found = False
    for inedge in self.get_incoming_edges():
      if not in_edge_found:
        in_edge_found = True
        result += '\nInEdge:'
      result += '\n  '+str(inedge)
    out_edge_found = False
    for outedge in self.get_outgoing_edges():
      if not out_edge_found:
        out_edge_found = True
        result += '\nOutEdge:'
      result += '\n  '+str(outedge)
    return result

class GenericEdgeBase:
  _srcedgenode : IListNode
  _destedgenode : IListNode

  def get_edge_label(self) -> str:
    return self.__class__.__name__ + ' ' + hex(id(self))
  def get_edge_description(self) -> typing.Iterable[str] | None:
    return None

  def __init__(self) -> None:
    self._srcedgenode = IListNode()
    self._destedgenode = IListNode()
    self._srcedgenode.value = self
    self._destedgenode.value = self

  def get_source_node(self) -> GenericNodeBase:
    return self._srcedgenode.parent

  def get_dest_node(self) -> GenericNodeBase:
    return self._destedgenode.parent

  def set_source_node(self, newsrc : GenericNodeBase):
    self._srcedgenode.remove_from_parent()
    newsrc._outgoingedges.push_back(self._srcedgenode)

  def set_dest_node(self, newdest : GenericNodeBase):
    self._destedgenode.remove_from_parent()
    newdest._incomingedges.push_back(self._destedgenode)

  def __str__(self) -> str:
    return self.get_edge_label() + ': ' + self.get_source_node().get_node_label() + ' --> ' + self.get_dest_node().get_node_label()

class GenericGraphBase:
  _all_nodes : IList[GenericNodeBase, GenericGraphBase]

  def get_entry_nodes(self) -> typing.Iterable[GenericNodeBase] | GenericNodeBase:
    return tuple()

  def get_graph_label(self) -> str:
    return self.__class__.__name__ + ' ' + hex(id(self))

  def __init__(self) -> None:
    self._all_nodes = IList(self)

  def get_all_nodes(self) -> typing.Iterable[GenericNodeBase]:
    return self._all_nodes

  def add_node(self, node : GenericNodeBase):
    assert node.parent is None
    self._all_nodes.push_back(node)

  def __str__(self) -> str:
    return self.get_graph_label()

  def get_graphviz_dot_source(self) -> str:
    exporter = GraphvizDotGraphExporter(self)
    visitor = GraphVisitor()
    visitor.visit(self, exporter)
    return exporter.dot.source

  def dump_graphviz_dot(self) -> None:
    dump_graphviz_dot(self, self.__class__.__name__)

# ----------------------------------------------------------
# 图外的类
# ----------------------------------------------------------

class GraphExporter:
  # 用来输出图的基类
  # 比如下面有个用于 Graphviz Dot 输出的子类
  def handle_node(self, node : GenericNodeBase):
    print(str(node))
  def handle_edge(self, edge : GenericEdgeBase):
    print(str(edge))
  def initialize(self, graph : GenericGraphBase):
    print(str(graph))
  def finalize(self, graph : GenericGraphBase):
    pass

class GraphVisitor:
  # 我们用来遍历图的基类
  # 如果我们不想输出所有图中元素，我们需要继承该类
  exporter : GraphExporter | None = None
  def __init__(self) -> None:
    self.exporter = None
  def should_exclude_node(self, node : GenericNodeBase):
    return False
  def should_exclude_node_incoming_edges(self, node : GenericNodeBase):
    return False
  def should_exclude_node_outgoing_edges(self, node : GenericNodeBase):
    return False
  def should_exclude_edge(self, edge : GenericEdgeBase):
    return False
  def should_include_unreachable_nodes(self):
    return True

  def visit(self, graph : GenericGraphBase, exporter : GraphExporter):
    visited_elements = set()
    worklist : collections.deque[GenericNodeBase] = collections.deque()
    def enqueue_node(node : GenericNodeBase):
      if node in visited_elements:
        return
      visited_elements.add(node)
      if self.should_exclude_node(node):
        return
      worklist.append(node)
    def enqueue_edge(edge : GenericEdgeBase, curnode : GenericNodeBase) -> bool:
      if edge in visited_elements:
        return False
      visited_elements.add(edge)
      if self.should_exclude_edge(edge):
        return False
      src = edge.get_source_node()
      if src is not curnode and self.should_exclude_node(src):
        return False
      dest = edge.get_dest_node()
      if dest is not curnode and self.should_exclude_node(dest):
        return False
      return True
    def mainloop():
      while len(worklist) > 0:
        n = worklist.popleft()
        exporter.handle_node(n)
        if not self.should_exclude_node_incoming_edges(n):
          for e in n.get_incoming_edges():
            if enqueue_edge(e, n):
              exporter.handle_edge(e)
              enqueue_node(e.get_source_node())
        if not self.should_exclude_node_outgoing_edges(n):
          for e in n.get_outgoing_edges():
            if enqueue_edge(e, n):
              exporter.handle_edge(e)
              enqueue_node(e.get_dest_node())

    startnodes = graph.get_entry_nodes()
    if isinstance(startnodes, GenericNodeBase):
      enqueue_node(startnodes)
    else:
      for n in startnodes:
        enqueue_node(n)
    mainloop()
    if self.should_include_unreachable_nodes():
      if allnodes := graph.get_all_nodes():
        for n in allnodes:
          enqueue_node(n)
        mainloop()
    exporter.finalize(graph)

class GraphvizDotGraphExporter(GraphExporter):
  dot : graphviz.Digraph
  graph : GenericGraphBase
  namecache : dict[GenericNodeBase, str]
  typecounts : dict[type, int]
  nodecolors : dict[type, str]
  edge_stypes : dict[type, dict]

  def __init__(self, graph : GenericGraphBase) -> None:
    super().__init__()
    self.graph = graph
    self.dot = graphviz.Digraph(name=graph.get_graph_label())
    self.namecache = dict()
    self.typecounts = dict()
    self.nodecolors = dict()
    self.edge_stypes = dict()

  def set_node_colors(self, d : dict[type, str]) -> None:
    self.nodecolors = d

  def set_edge_styles(self, d : dict[type, dict]) -> None:
    self.edge_stypes = d

  def _incr_type_count(self, t : type) -> int:
    if t in self.typecounts:
      self.typecounts[t] += 1
      return self.typecounts[t]
    self.typecounts[t] = 0
    return 0

  def _get_node_id(self, node : GenericNodeBase) -> str:
    if node not in self.namecache:
      basename = type(node).__name__
      index = self._incr_type_count(type(node))
      idstr = basename + str(index)
      self.namecache[node] = idstr
      return idstr
    return self.namecache[node]

  def _get_node_label(self, node : GenericNodeBase) -> str:
    result = node.get_node_label()
    if desc := node.get_node_description():
      result += '|' + '|'.join(desc)
    return result

  def _get_edge_label(self, edge : GenericEdgeBase) -> str:
    result = edge.get_edge_label()
    if desc := edge.get_edge_description():
      result += '|' + '|'.join(desc)
    return result

  def handle_node(self, node : GenericNodeBase):
    idstr = self._get_node_id(node)
    node_attrs = {'shape' : 'record'}
    if c := self.nodecolors.get(type(node)):
      node_attrs['color'] = c
    self.dot.node(name=idstr, label=self._get_node_label(node), **node_attrs)

  def handle_edge(self, edge : GenericEdgeBase):
    edge_attrs = self.edge_stypes.get(type(edge))
    if edge_attrs is None:
      edge_attrs = {}
    elif callable(edge_attrs):
      edge_attrs = edge_attrs(edge)
    assert isinstance(edge_attrs, dict)
    self.dot.edge(tail_name=self._get_node_id(edge.get_source_node()), head_name=self._get_node_id(edge.get_dest_node()), label=self._get_edge_label(edge), **edge_attrs)

  def finalize(self, graph : GenericGraphBase):
    pass

_TR_graph = TranslationDomain("graph")
_TR_graph_dot_dump = _TR_graph.tr("graphviz_dot_dump",
  en="Graphviz DOT dump at: ",
  zh_cn="Graphviz DOT 导出文件保存在该位置：",
  zh_hk="Graphviz DOT 導出文件保存在該位置：",
)

def dump_graphviz_dot(graph : GenericGraphBase, name : str):
  name_portion = 'anon'
  if len(name) > 0:
    sanitized_name = get_sanitized_filename(name)
    if len(sanitized_name) > 0:
      name_portion = sanitized_name
  file = tempfile.NamedTemporaryFile('w', suffix='.dot', prefix='preppipe_' + name_portion + '_', delete=False)
  file.write(graph.get_graphviz_dot_source())
  file.close()
  path = os.path.abspath(file.name)
  print(_TR_graph_dot_dump.get() + path)

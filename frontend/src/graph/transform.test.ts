import { describe, expect, it } from 'vitest';

import type { GraphDocument } from '../api/types';
import { toElements } from './transform';

const empty: GraphDocument = {
  nodes: [],
  edges: [],
  meta: {
    node_count: 0,
    edge_count: 0,
    cycles: [],
    isolated_nodes: [],
    parse_failures: 0,
    ambiguous_imports: 0,
    unresolved_imports: 0,
    analyzed_at: null,
  },
};

const tree: GraphDocument = {
  ...empty,
  nodes: [
    { id: 'repo:.', type: 'repo', label: 'sample', properties: {} },
    { id: 'dir:src', type: 'directory', label: 'src', properties: {} },
    { id: 'file:src/app.py', type: 'file', label: 'app.py', properties: {} },
  ],
  edges: [
    { source: 'repo:.', target: 'dir:src', type: 'contains', properties: {} },
    {
      source: 'dir:src',
      target: 'file:src/app.py',
      type: 'contains',
      properties: {},
    },
  ],
};

describe('toElements', () => {
  it('keeps the node id, label and type', () => {
    expect(toElements(tree).nodes[0]).toEqual({
      data: { id: 'repo:.', label: 'sample', type: 'repo' },
    });
  });

  it('leaves out parseError when the file parsed fine', () => {
    expect(toElements(tree).nodes[0].data).not.toHaveProperty('parseError');
  });

  it('gives every edge an id, which the API does not provide', () => {
    expect(toElements(tree).edges[0]).toEqual({
      data: {
        id: 'contains:repo:.->dir:src',
        source: 'repo:.',
        target: 'dir:src',
        type: 'contains',
        count: 1,
        details: [],
      },
    });
  });

  it('merges parallel edges into one and counts them', () => {
    const parallel: GraphDocument = {
      ...empty,
      nodes: [
        { id: 'file:a.py', type: 'file', label: 'a.py', properties: {} },
        { id: 'file:b.py', type: 'file', label: 'b.py', properties: {} },
      ],
      edges: [
        {
          source: 'file:a.py',
          target: 'file:b.py',
          type: 'imports',
          properties: { name: 'Edge', line: 3 },
        },
        {
          source: 'file:a.py',
          target: 'file:b.py',
          type: 'imports',
          properties: { name: 'Node', line: 3 },
        },
      ],
    };

    const edges = toElements(parallel).edges;

    expect(edges).toHaveLength(1);
    expect(edges[0].data.count).toBe(2);
    // 細節沒丟，只是收進 data 裡
    expect(edges[0].data.details).toEqual([
      { from: 'file:a.py', to: 'file:b.py', line: 3, names: ['Edge', 'Node'] },
    ]);
  });

  it('unfolds the sources a collapsed edge carries, grouped by file pair', () => {
    const collapsed: GraphDocument = {
      ...empty,
      nodes: [
        { id: 'dir:a', type: 'directory', label: 'a', properties: {} },
        { id: 'dir:b', type: 'directory', label: 'b', properties: {} },
      ],
      edges: [
        {
          source: 'dir:a',
          target: 'dir:b',
          type: 'imports',
          properties: {
            weight: 3,
            sources: [
              { from: 'file:a/one.py', to: 'file:b/x.py', name: 'Edge', line: 1 },
              { from: 'file:a/one.py', to: 'file:b/x.py', name: 'Node', line: 1 },
              { from: 'file:a/two.py', to: 'file:b/x.py', module: 'b.x', line: 4 },
            ],
          },
        },
      ],
    };

    const edges = toElements(collapsed).edges;

    expect(edges[0].data.count).toBe(3);
    expect(edges[0].data.details).toEqual([
      { from: 'file:a/one.py', to: 'file:b/x.py', line: 1, names: ['Edge', 'Node'] },
      // 沒有 name 的 import 退回模組字串，不會變成空白
      { from: 'file:a/two.py', to: 'file:b/x.py', line: 4, names: ['b.x'] },
    ]);
  });

  it('splits one file pair into two groups when it imports on two lines', () => {
    const twice: GraphDocument = {
      ...empty,
      nodes: [
        { id: 'dir:a', type: 'directory', label: 'a', properties: {} },
        { id: 'dir:b', type: 'directory', label: 'b', properties: {} },
      ],
      edges: [
        {
          source: 'dir:a',
          target: 'dir:b',
          type: 'imports',
          properties: {
            weight: 2,
            sources: [
              { from: 'file:a/one.py', to: 'file:b/x.py', name: 'Edge', line: 1 },
              { from: 'file:a/one.py', to: 'file:b/x.py', name: 'Node', line: 9 },
            ],
          },
        },
      ],
    };

    expect(toElements(twice).edges[0].data.details).toEqual([
      { from: 'file:a/one.py', to: 'file:b/x.py', line: 1, names: ['Edge'] },
      { from: 'file:a/one.py', to: 'file:b/x.py', line: 9, names: ['Node'] },
    ]);
  });

  it('gives contains edges no details', () => {
    expect(toElements(tree).edges.every((edge) => edge.data.details.length === 0)).toBe(
      true,
    );
  });

  it('does not merge edges of different types', () => {
    const mixed: GraphDocument = {
      ...empty,
      nodes: [
        { id: 'dir:a', type: 'directory', label: 'a', properties: {} },
        { id: 'file:a/b.py', type: 'file', label: 'b.py', properties: {} },
      ],
      edges: [
        { source: 'dir:a', target: 'file:a/b.py', type: 'contains', properties: {} },
        { source: 'dir:a', target: 'file:a/b.py', type: 'imports', properties: {} },
      ],
    };

    expect(toElements(mixed).edges).toHaveLength(2);
  });

  it('carries a parse error onto the node so it can be drawn differently', () => {
    const broken: GraphDocument = {
      ...empty,
      nodes: [
        {
          id: 'file:broken.py',
          type: 'file',
          label: 'broken.py',
          properties: { parse_error: 'invalid syntax (line 2)' },
        },
      ],
    };

    expect(toElements(broken).nodes[0].data.parseError).toBe('invalid syntax (line 2)');
  });

  it('produces the same ids every time', () => {
    expect(toElements(tree)).toEqual(toElements(tree));
  });

  it('keeps the order the API sent', () => {
    expect(toElements(tree).nodes.map((node) => node.data.id)).toEqual([
      'repo:.',
      'dir:src',
      'file:src/app.py',
    ]);
  });

  it('handles an empty graph', () => {
    expect(toElements(empty)).toEqual({ nodes: [], edges: [] });
  });
});

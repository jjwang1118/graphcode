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
        detail: '',
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
    expect(edges[0].data.detail).toBe('Edge 行 3\nNode 行 3');
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

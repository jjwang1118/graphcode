"""引用事實 → `imports` 邊 ＋ `external_package` 節點。

薄殼：真正的名稱解析在 `app/resolve/`，這裡只負責把它接上產生器的形狀——
`ResolveResult` 的兩個指標換成 `counters`，key 用 `Diagnostics` 的欄位名。

**resolve 仍然是獨立的一層**（獨立測試、獨立文件），只是不再由 `pipeline.py`
直接呼叫，而是被這個產生器叫到。規格見 docs/backend/resolve.md。
"""

from collections.abc import Mapping, Sequence

from app.facts.production import Context, Production
from app.parsers import Import
from app.resolve import to_edges


class ImportProducer:
    def produce(
        self, facts: Mapping[str, Sequence[Import]], context: Context
    ) -> Production:
        resolved = to_edges(facts, context.index, context.language.resolver)
        return Production(
            nodes=resolved.nodes,
            edges=resolved.edges,
            counters={
                "ambiguous_imports": resolved.ambiguous,
                "unresolved_imports": resolved.unresolved,
            },
        )

// Explorer — file tree of the active repository's workspace; opens files in the editor.
import { useEffect, useState } from "react";
import { api, type FileNode } from "../../api/client";
import { useRepo } from "../../context/RepoContext";
import { useWorkbench } from "../../context/WorkbenchContext";
import { fileIcon } from "../../lib/fileIcons";
import { t } from "../../theme";

function TreeNode({ node, depth }: { node: FileNode; depth: number }) {
  const { activeId } = useRepo();
  const { openFile, activePath } = useWorkbench();
  const [open, setOpen] = useState(depth < 1);
  const isDir = node.type === "dir";
  const selected = activePath === node.path;

  const rowStyle: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: 5, cursor: "pointer",
    padding: "2px 6px", paddingLeft: 6 + depth * 12, fontSize: 13,
    color: selected ? t.text : t.textDim, whiteSpace: "nowrap",
    background: selected ? t.bgHover : "transparent", fontFamily: t.sans,
  };

  return (
    <div>
      <div style={rowStyle}
        onClick={() => (isDir ? setOpen((o) => !o) : activeId && openFile({ repoId: activeId, path: node.path, name: node.name }))}
        onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = "#ffffff08"; }}
        onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = "transparent"; }}>
        <span style={{ width: 10, fontSize: 9, color: t.textDim }}>{isDir ? (open ? "▼" : "▶") : ""}</span>
        <span style={{ fontSize: 13 }}>{isDir ? (open ? "📂" : "📁") : fileIcon(node.name)}</span>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{node.name}</span>
      </div>
      {isDir && open && node.children?.map((c) => <TreeNode key={c.path} node={c} depth={depth + 1} />)}
    </div>
  );
}

export default function Explorer() {
  const { activeId, repos } = useRepo();
  const [tree, setTree] = useState<FileNode[] | null>(null);
  const [root, setRoot] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeId) { setTree(null); return; }
    setLoading(true); setErr(null);
    api.fileTree(activeId)
      .then((r) => { setTree(r.tree); setRoot(r.root); })
      .catch((e) => setErr(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, [activeId]);

  const repoName = repos.find((r) => r.id === activeId)?.url?.split("/").pop() ?? root ?? "EXPLORER";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ padding: "8px 12px 4px", fontSize: 11, fontWeight: 700, letterSpacing: 0.6,
        color: t.textDim, textTransform: "uppercase" }}>Explorer</div>
      <div style={{ padding: "2px 12px 6px", fontSize: 11, fontWeight: 700, color: t.text,
        textTransform: "uppercase", letterSpacing: 0.4 }}>{repoName}</div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto", paddingBottom: 8 }}>
        {!activeId && <div style={{ color: t.textDim, fontSize: 12, padding: 12 }}>No repository selected.</div>}
        {loading && <div style={{ color: t.textDim, fontSize: 12, padding: 12 }}>Loading files…</div>}
        {err && <div style={{ color: t.red, fontSize: 12, padding: 12 }}>Could not load files: {err}</div>}
        {tree?.map((n) => <TreeNode key={n.path} node={n} depth={0} />)}
        {tree && tree.length === 0 && <div style={{ color: t.textDim, fontSize: 12, padding: 12 }}>Empty workspace.</div>}
      </div>
    </div>
  );
}

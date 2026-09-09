import { useState } from "react";

/** Toggle a Set of string keys (e.g. filenames or commit SHAs). */
export function useExpandableSet(initialKeys = []) {
  const [openKeys, setOpenKeys] = useState(() => new Set(initialKeys));

  const toggle = (key) => {
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = (keys) => setOpenKeys(new Set(keys));
  const collapseAll = () => setOpenKeys(new Set());

  return { openKeys, toggle, expandAll, collapseAll, setOpenKeys };
}

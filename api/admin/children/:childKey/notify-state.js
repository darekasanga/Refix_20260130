export default function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method Not Allowed" });
  }

  // childKey は URL エンコードされて来る想定
  const { childKey } = req.query;
  const decoded = decodeURIComponent(childKey || "");
  const parts = decoded.split("||"); // ["園名","クラス名","園児ID"] 想定

  // まずは暫定で 200 を返して 404 を止める（本実装は後でOK）
  return res.status(200).json({
    ok: true,
    childKey: decoded,
    parsed: { school: parts[0] || null, class: parts[1] || null, child: parts[2] || null },
    notifyState: {
      // 仮：UI が壊れない最小レスポンスにする
      enabled: false,
    },
  });
}

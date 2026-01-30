export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method Not Allowed" });
  }

  // JSON を受ける（Vercel Functions は基本 JSON OK）
  const body = req.body ?? null;

  // まずは暫定で 200 を返して 404 と NOT_FOUND トーストを止める
  return res.status(200).json({
    ok: true,
    message: "stub upsert success",
    received: body,
  });
}

// EnerX - verification du hash d'un rapport (Node.js, aucune dependance)
// Usage :  node verify_hash.js demo_report.json
// A copier cote backend / front : meme regle que aggregator.hash_report (Python).
const fs = require("fs");
const crypto = require("crypto");

// Nombre -> texte decimal fixe : 6 decimales, zeros de fin retires (5939 -> "5939", 0.00001 -> "0.00001")
function canonNumber(x) {
  if (!Number.isFinite(x)) throw new Error("Valeur non finie dans le rapport");
  let s = x.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return s === "" || s === "-0" ? "0" : s;
}

// Remplace chaque nombre par son texte canonique et trie les cles de chaque objet
function canon(v) {
  if (typeof v === "number") return canonNumber(v);
  if (Array.isArray(v)) return v.map(canon);
  if (v && typeof v === "object") {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = canon(v[k]);
    return out;
  }
  return v; // string, boolean, null
}

function hashReport(report) {
  const { report_hash, ...body } = report;
  // JSON.stringify : compact, UTF-8 sans echappement des accents (comme ensure_ascii=False)
  const canonical = JSON.stringify(canon(body));
  return crypto.createHash("sha256").update(canonical, "utf8").digest("hex");
}

if (require.main === module) {
  const report = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const computed = hashReport(report);
  console.log("Hash du rapport : ", report.report_hash);
  console.log("Hash recalcule  : ", computed);
  console.log(computed === report.report_hash ? "OK : rapport intact" : "ECHEC : rapport modifie ou regle differente");
  process.exit(computed === report.report_hash ? 0 : 1);
}
module.exports = { hashReport };

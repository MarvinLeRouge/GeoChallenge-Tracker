import type { FastAPIValidationItem, FastAPIErrorDetail } from "@/types/http";

export const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null;

export const isValidationItem = (x: unknown): x is FastAPIValidationItem =>
  isObject(x) &&
  (("msg" in x && (x as Record<string, unknown>).msg === undefined) ||
    typeof (x as Record<string, unknown>).msg === "string" ||
    ("loc" in x && Array.isArray((x as Record<string, unknown>).loc)));

/** Lit l'enveloppe backend `{ success: false, error: { code, message, details? } }` */
const getEnvelopeDetail = (d: Record<string, unknown>): FastAPIErrorDetail => {
  const err = d.error;
  if (!isObject(err)) return undefined;
  if (Array.isArray(err.details) && err.details.length > 0)
    return err.details.filter(isObject).map((x) => ({
      loc: typeof x.field === "string" ? x.field.split(" -> ") : undefined,
      msg: typeof x.message === "string" ? x.message : undefined,
      type: typeof x.type === "string" ? x.type : undefined,
    }));
  return typeof err.message === "string" ? err.message : undefined;
};

/** Extrait le détail d'une erreur API : enveloppe backend, sinon `detail`/`msg` FastAPI bruts */
export const getDetail = (d: unknown): FastAPIErrorDetail => {
  if (!isObject(d)) return undefined;
  const envelope = getEnvelopeDetail(d);
  if (envelope !== undefined) return envelope;
  const raw = (d as Record<string, unknown>).detail;
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw) && raw.every(isValidationItem)) return raw;

  const msg = (d as Record<string, unknown>).msg;
  if (typeof msg === "string") return msg;

  return undefined;
};

/** Convertit un detail en texte lisible (pour toasts/logs) */
export const detailToText = (d: FastAPIErrorDetail): string => {
  if (typeof d === "string") return d;
  if (Array.isArray(d))
    return d
      .map((x) => x.msg ?? "")
      .filter(Boolean)
      .join("\n");
  return "";
};

/** Message lisible d'une erreur de requête (axios ou objet `{ response: { data } }`), sinon undefined */
export const apiErrorMessage = (e: unknown): string | undefined => {
  const data =
    isObject(e) && isObject(e.response) ? e.response.data : undefined;
  return detailToText(getDetail(data)) || undefined;
};

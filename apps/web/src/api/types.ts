import type { components } from "./schema";

type S = components["schemas"];

export type TokenResponse = S["TokenResponse"];
export type RegisterRequest = S["RegisterRequest"];
export type LoginRequest = S["LoginRequest"];
export type UserOut = S["UserOut"];
export type UserUpdate = S["UserUpdate"];
export type CustomerOut = S["CustomerOut"];
export type CustomerCreate = S["CustomerCreate"];
export type CustomerUpdate = S["CustomerUpdate"];
export type QuoteOut = S["QuoteOut"];
export type QuoteSummary = S["QuoteSummary"];
export type QuoteCreate = S["QuoteCreate"];
export type QuoteUpdate = S["QuoteUpdate"];
export type QuoteLineItemIn = S["QuoteLineItemIn"];
export type QuoteLineItemOut = S["QuoteLineItemOut"];
export type AuditFlagOut = S["AuditFlagOut"];
export type GenerateRequest = S["GenerateRequest"];
export type AnswerQuestionRequest = S["AnswerQuestionRequest"];
export type GenerationResponse = S["GenerationResponse"];
export type MarkStatusRequest = S["MarkStatusRequest"];
export type OverrideFlagRequest = S["OverrideFlagRequest"];

export type Province = UserOut["province"];
export type Language = UserOut["language"];
export type QuoteStatus = QuoteSummary["status"];

export const PROVINCES: Province[] = ["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"];

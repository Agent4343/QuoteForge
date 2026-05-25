import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, postForm } from "./client";
import type {
  AnswerQuestionRequest,
  CustomerCreate,
  CustomerOut,
  CustomerUpdate,
  GenerateRequest,
  GenerationResponse,
  LoginRequest,
  QuoteCreate,
  QuoteOut,
  QuoteSummary,
  QuoteUpdate,
  RegisterRequest,
  TokenResponse,
  UserOut,
  UserUpdate,
} from "./types";

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<UserOut>("/api/me"),
    enabled,
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: (body: LoginRequest) => api.post<TokenResponse>("/api/auth/login", body, false),
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: RegisterRequest) =>
      api.post<TokenResponse>("/api/auth/register", body, false),
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserUpdate) => api.patch<UserOut>("/api/me", body),
    onSuccess: (u) => qc.setQueryData(["me"], u),
  });
}

export function useUploadLogo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return postForm<UserOut>("/api/me/logo", form);
    },
    onSuccess: (u) => qc.setQueryData(["me"], u),
  });
}

export function useCustomers() {
  return useQuery({ queryKey: ["customers"], queryFn: () => api.get<CustomerOut[]>("/api/customers") });
}

export function useCustomer(id: string | undefined) {
  return useQuery({
    queryKey: ["customer", id],
    queryFn: () => api.get<CustomerOut>(`/api/customers/${id}`),
    enabled: !!id,
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerCreate) => api.post<CustomerOut>("/api/customers", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useUpdateCustomer(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerUpdate) => api.patch<CustomerOut>(`/api/customers/${id}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customers"] });
      void qc.invalidateQueries({ queryKey: ["customer", id] });
    },
  });
}

export function useDeleteCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`/api/customers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useQuotes(status?: string) {
  return useQuery({
    queryKey: ["quotes", status ?? "all"],
    queryFn: () =>
      api.get<QuoteSummary[]>(`/api/quotes${status ? `?status=${status}` : ""}`),
  });
}

export function useQuote(id: string | undefined) {
  return useQuery({
    queryKey: ["quote", id],
    queryFn: () => api.get<QuoteOut>(`/api/quotes/${id}`),
    enabled: !!id,
  });
}

export function useCreateQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: QuoteCreate) => api.post<QuoteOut>("/api/quotes", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quotes"] }),
  });
}

interface CodeEdition {
  label: string;
  base_cec?: string | null;
  effective_date?: string | null;
}
interface Bilingual {
  en: string;
  fr: string;
}
export interface ProvinceCode {
  regulator: Bilingual;
  permit_model: Bilingual;
  utility: string | null;
  customer_language_default: string;
  current_edition: CodeEdition;
  pending_edition: CodeEdition | null;
  transition: { start: string; end: string } | null;
}

export function useCodeEditions() {
  return useQuery({
    queryKey: ["code-editions"],
    queryFn: () => api.get<{ provinces: Record<string, ProvinceCode> }>("/api/code-editions"),
  });
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<DashboardStats>("/api/dashboard/stats") });
}

export function useAssemblyMetrics() {
  return useQuery({
    queryKey: ["dashboard", "assemblies"],
    queryFn: () => api.get<{ assemblies: AssemblyMetric[] }>("/api/dashboard/assemblies"),
  });
}

export interface DashboardStats {
  open_quotes: number;
  approved: number;
  declined: number;
  win_rate_pct: number | null;
  average_margin_pct: number | null;
  llm_cost_cad: number;
  llm_input_tokens: number;
  llm_output_tokens: number;
  ai_sessions: number;
}

export interface AssemblyMetric {
  assembly_id: string;
  name_en: string;
  name_fr: string;
  category: string | null;
  status: string;
  line_count: number;
  quote_count: number;
  total_quantity: number;
  edited_count: number;
  edit_rate_pct: number;
}

/** Quote mutations that return the updated quote; callers update the ["quote", id] cache. */
export function useQuoteActions(id: string) {
  const qc = useQueryClient();
  const onQuote = (q: QuoteOut) => {
    qc.setQueryData(["quote", id], q);
    void qc.invalidateQueries({ queryKey: ["quotes"] });
  };
  return {
    update: useMutation({
      mutationFn: (body: QuoteUpdate) => api.patch<QuoteOut>(`/api/quotes/${id}`, body),
      onSuccess: onQuote,
    }),
    recompute: useMutation({
      mutationFn: () => api.post<QuoteOut>(`/api/quotes/${id}/recompute`),
      onSuccess: onQuote,
    }),
    overrideFlag: useMutation({
      mutationFn: (flagId: string) =>
        api.post<QuoteOut>(`/api/quotes/${id}/override-flag`, { flag_id: flagId }),
      onSuccess: onQuote,
    }),
    finalize: useMutation({
      mutationFn: () => api.post<QuoteOut>(`/api/quotes/${id}/finalize`),
      onSuccess: onQuote,
    }),
    send: useMutation({
      mutationFn: () => api.post<QuoteOut>(`/api/quotes/${id}/send`),
      onSuccess: onQuote,
    }),
    markStatus: useMutation({
      mutationFn: (status: string) =>
        api.post<QuoteOut>(`/api/quotes/${id}/mark-status`, { status }),
      onSuccess: onQuote,
    }),
    generate: useMutation({
      mutationFn: (body: GenerateRequest) =>
        api.post<GenerationResponse>(`/api/quotes/${id}/generate`, body),
      onSuccess: (r) => onQuote(r.quote),
    }),
    answer: useMutation({
      mutationFn: (body: AnswerQuestionRequest) =>
        api.post<GenerationResponse>(`/api/quotes/${id}/answer-question`, body),
      onSuccess: (r) => onQuote(r.quote),
    }),
  };
}

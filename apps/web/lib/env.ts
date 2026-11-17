// Reads the Supabase settings and tells us whether they have been filled in.
export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

export const isSupabaseConfigured =
  /^https?:\/\//.test(supabaseUrl) &&
  !supabaseUrl.includes("your-project-id") &&
  supabaseKey.length > 20 &&
  !supabaseKey.includes("xxxx");

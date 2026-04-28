import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: process.env.VITE_OPENAPI_INPUT ?? 'http://localhost:8000/openapi.json',
  output: './src/api/generated',
})

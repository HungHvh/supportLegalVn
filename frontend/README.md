This is a [Next.js](https://nextjs.org) frontend for supportLegal.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

### API base URL

This app reads the backend origin from `NEXT_PUBLIC_API_BASE_URL`.

Create a local `.env.local` file with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

For Vercel production, set `NEXT_PUBLIC_API_BASE_URL` to your public API domain, for example:

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.domain.com
```

`NEXT_PUBLIC_API_BASE_URL` is required in production. If it is missing, the app will fail fast instead of silently falling back to localhost.

## Production deployment

- Deploy the frontend to Vercel.
- Set `NEXT_PUBLIC_API_BASE_URL` in the Vercel environment settings for each branch/environment.
- Keep `.env.local` for local development only.
- Do not hardcode `localhost` in production code paths.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

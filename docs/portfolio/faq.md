# FAQ

## Timeline
**Q: How long does a typical run take?**
A: 5–10 minutes for a full research report, 2–3 minutes for lead intel dossiers.

## Cost
**Q: What are the API costs?**
A: ~$0.30–$0.50 per report (OpenAI GPT-4o + Tavily + Firecrawl). Lead intel is cheaper (~$0.20).

## Customization
**Q: Can I add new verticals?**
A: Yes — add a new entry in `backend/configs/verticals.py` with input schema, prompt focus, and output sections. No pipeline changes needed.

## Privacy
**Q: Where does my data go?**
A: Uploaded PDFs are stored in `/tmp` and cleaned up after processing. Run data is stored in your PostgreSQL database. External API calls go to OpenAI, Tavily, and Firecrawl.

## Self-Hosting
**Q: Can I self-host this?**
A: Yes — see `docs/deployment.md`. You need a PostgreSQL instance, a server for the FastAPI backend, and Vercel (or any Node.js host) for the frontend.

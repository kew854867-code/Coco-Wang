"""Per-company tailored sentence (appended to the SUMMARY) and cover-letter hook.
Each line only connects verified resume facts to what the company/role does; edit freely."""
HOOKS = {
 "Datadog": ("Eager to bring a track record of turning developer and AI communities into packed, sponsor-backed events to Datadog's community and events programs.",
             "I would bring the same playbook I used to sell out the Humanity & AGI Summit at Stanford: a clear speaker thesis, tight content operations, and partners who co-promote."),
 "Cognition": ("Excited to help Cognition grow its developer community through events, drawing on 21+ community events hosted and a 52,000+ network.",
               "Cognition's developers and builders are exactly the audience I have spent the last two years convening in Silicon Valley, and I run my own content and outreach tooling with Claude every day."),
 "Anthropic": ("Motivated to support Anthropic's partnerships and ecosystem growth, with daily hands-on use of Claude to build my own outreach and content tools.",
               "I already use Claude daily to build my Outreach Agent, which opened 715 LinkedIn conversations, and I want to apply that partner-outreach discipline at Anthropic."),
 "Harvey": ("Keen to grow Harvey's community and content presence, building on 3,000+ LinkedIn followers and an automated content pipeline I built and run.",
            "I run an end-to-end content pipeline for a 3,000+ LinkedIn audience and know how to turn community moments into content that compounds."),
 "Cartesia": ("Interested in helping Cartesia's go-to-market and partnerships through executive outreach, CRM discipline and sponsor-led event experience.",
              "My background is in the executive outreach, CRM-tracked pipeline and partner-led events that early-stage AI companies need to build market presence."),
 "Brex": ("Excited to deepen Brex's startup and venture relationships, building on investor outreach to 20+ VC firms and a founder-facing event portfolio.",
          "I have coordinated outreach to 20+ VC firms and run founder-facing events as Co-Founder of Rwawa, which maps directly onto Brex's startup and venture partnerships."),
 "Lambda": ("Eager to support Lambda's developer relations by connecting AI builders through events and community programs.",
            "I know the AI and robotics builder community in the Bay Area and the faculty and founders it listens to, and I would bring that network to Lambda's developer programs."),
 "Cursor (Anysphere)": ("Excited to build Cursor's startup events and community, drawing on 21 hosted events and a founder and builder network across Silicon Valley.",
                        "I have hosted 21 events for founders and builders and am a daily user of AI coding and agent tools, which keeps me close to how this community actually works."),
 "Vercel": ("Interested in driving Vercel's partner pipeline with the same executive outreach and CRM-tracked follow-up I used to open 715 LinkedIn conversations.",
            "My outreach tooling and CRM-driven follow-up produced 715 conversations with about a one-third reply rate, which is the kind of top-of-funnel engine this role needs."),
 "Snowflake": ("Excited to bring large-room event production and sponsorship experience to Snowflake's strategic events.",
               "I have produced sold-out events of 500+ attendees with 40+ speakers and secured sponsors such as Tencent and Faraday Future, so strategic event execution is my core skill."),
 "Scale AI": ("Eager to contribute to Scale AI's community and field events, with a robotics and embodied-AI network from the Bay Area ecosystem.",
              "Scale's push into physical AI lines up with the embodied-AI community I track weekly through my robotics events calendar and where I have built relationships with founders and faculty."),
 "Skydio": ("Interested in Skydio's partnerships and business development, backed by robotics-industry executive outreach and sponsor negotiation.",
            "I have closed sponsor and exhibitor deals in the robotics industry and speak the language of robotics founders and executives."),
}
GENERIC = ("Motivated by the opportunity to apply my robotics and AI community-building experience to {company}'s {function}.",
           "I would like to bring my robotics and AI community experience to {company}.")
def function_of(title):
    t = title.lower()
    for k, v in [("event", "events"), ("community", "community"), ("developer", "developer relations"), ("partner", "partnerships"),
                 ("business development", "business development"), ("startup", "startup programs"), ("marketing", "marketing")]:
        if k in t: return v
    return "team"
def hook(company, title):
    if company in HOOKS: return HOOKS[company]
    f = function_of(title)
    return GENERIC[0].format(company=company, function=f), GENERIC[1].format(company=company)

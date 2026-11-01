// Offline prewarm/cleanup check. Never launches or attaches to the game.
#include "identity.h"
#include "glyph_cache.h"
#include <iostream>
#include <memory>

int wmain(int argc, wchar_t** argv) {
    using namespace u9cht;
    try {
        require(argc == 4,"usage: U9ChtShowcaseCheck PACK FONT FRESH_JSONL");
        auto pack = std::make_unique<Pack>(); pack->load(argv[1],true);
        require(pack->glyph_count && pack->glyph_count*2 <= GlyphCacheCapacity,"showcase cache capacity");
        auto cache = std::make_unique<GlyphCache>(); cache->open(argv[2]);
        Logger log; log.open(argv[3],true);
        for (uint32_t i = 0; i < pack->glyph_count; ++i) {
            const auto scalar = pack->scalars[i];
            for (auto em : {20U,40U}) {
                cache->warm(scalar,em); const auto* g = cache->get(scalar,em);
                require(g && g->advance > 0,"missing glyph");
                log.event("offline_glyph", "\"scalar\":"+std::to_string(scalar)+
                    ",\"em\":"+std::to_string(em)+",\"advance\":"+std::to_string(g->advance)+
                    ",\"coverage_sha256\":\""+utf8(sha256_bytes(g->alpha.data(),g->alpha.size()))+"\"");
            }
            const auto* a = cache->get(scalar,20); const auto* b = cache->get(scalar,40);
            require(a->advance*16/20 == b->advance*16/40,"inconsistent logical advances");
        }
        const auto expected = pack->glyph_count*2;
        require(cache->size() == expected && cache->misses == expected,"unexpected warm misses");
        for (uint32_t i = 0; i < pack->glyph_count; ++i) for (auto em : {20U,40U}) {
            const auto* first = cache->get(pack->scalars[i],em);
            cache->warm(pack->scalars[i],em);
            require(cache->get(pack->scalars[i],em) == first,"cache entry not reused");
        }
        require(cache->misses == expected && cache->size() == expected,"cache grew on reuse");
        require(cache->close() && cache->size() == 0,"private font/cache cleanup failed");
        log.event("offline_pass","\"plans\":"+std::to_string(pack->count)+
            ",\"glyphs\":"+std::to_string(pack->glyph_count)+",\"cache_entries\":"+
            std::to_string(expected)+",\"capacity\":"+std::to_string(GlyphCacheCapacity)+
            ",\"private_font_removed\":true,\"game_launched\":false");
        require(!log.failures(),"offline evidence write failed");
        std::cout << "PASS: offline selected-pack/font/advances/prewarm/reuse/cleanup; no game launched\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}

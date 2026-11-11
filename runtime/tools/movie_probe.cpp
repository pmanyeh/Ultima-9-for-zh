// LOCAL-ONLY check: decodes a whole movie with pl_mpeg (no window, no audio device) and prints what it found.
// U9ChtMovieProbe MOVIE.dat  ->  width height fps duration video_frames audio_seconds first_frame_fnv
#include <cstdio>
#include "pl_mpeg.h"
#include <cstdint>
#include <vector>

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) { std::fprintf(stderr,"usage: U9ChtMovieProbe MOVIE.dat\n"); return 2; }
    FILE* f = nullptr;
    if (_wfopen_s(&f,argv[1],L"rb") || !f) { std::fprintf(stderr,"cannot open\n"); return 1; }
    plm_t* plm = plm_create_with_file(f,1);
    if (!plm || !plm_probe(plm,5000*1024)) { std::fprintf(stderr,"not MPEG-1 PS\n"); return 1; }
    const int w = plm_get_width(plm), h = plm_get_height(plm);
    plm_set_audio_enabled(plm,1);
    std::vector<uint8_t> bgra(size_t(w)*h*4);
    uint64_t frames = 0, samples = 0, fnv = 14695981039346656037ULL;
    while (plm_frame_t* fr = plm_decode_video(plm)) {
        if (frames == 0) { plm_frame_to_bgra(fr,bgra.data(),w*4); for (auto b : bgra) { fnv ^= b; fnv *= 1099511628211ULL; } }
        ++frames;
    }
    plm_rewind(plm);
    plm_set_video_enabled(plm,0);
    while (plm_samples_t* s = plm_decode_audio(plm)) samples += s->count;
    const int rate = plm_get_samplerate(plm);
    std::printf("%d %d %.3f %.3f %llu %.3f %016llx\n",w,h,plm_get_framerate(plm),plm_get_duration(plm),
        (unsigned long long)frames, rate ? double(samples)/rate : 0.0, (unsigned long long)fnv);
    plm_destroy(plm);
    return 0;
}

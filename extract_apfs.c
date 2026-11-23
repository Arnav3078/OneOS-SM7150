#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <time.h>
#include "lzfse.h"

#pragma pack(push, 1)
typedef struct {
    uint32_t ctype;
    uint32_t reserved;
    uint64_t sector_num;
    uint64_t sector_count;
    uint64_t comp_off;
    uint64_t comp_len;
} ChunkDesc;
#pragma pack(pop)

#define BLOCK_SIZE (1024 * 1024) // 1 MB streaming block

int main(int argc, char *argv[]) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <dmg_file> <chunks.bin> <output_raw_img>\n", argv[0]);
        return 1;
    }

    const char *dmg_path = argv[1];
    const char *chunks_path = argv[2];
    const char *out_path = argv[3];

    FILE *cf = fopen(chunks_path, "rb");
    if (!cf) {
        perror("Failed to open chunks.bin");
        return 1;
    }
    char magic[4];
    if (fread(magic, 1, 4, cf) != 4 || memcmp(magic, "APFS", 4) != 0) {
        fprintf(stderr, "Invalid magic in chunks.bin\n");
        fclose(cf);
        return 1;
    }
    uint32_t num_chunks = 0;
    if (fread(&num_chunks, 4, 1, cf) != 1) {
        fprintf(stderr, "Failed to read num_chunks\n");
        fclose(cf);
        return 1;
    }

    ChunkDesc *chunks = malloc(num_chunks * sizeof(ChunkDesc));
    if (!chunks) {
        fprintf(stderr, "Out of memory for chunks\n");
        fclose(cf);
        return 1;
    }
    if (fread(chunks, sizeof(ChunkDesc), num_chunks, cf) != num_chunks) {
        fprintf(stderr, "Failed to read all chunk descriptors\n");
        free(chunks);
        fclose(cf);
        return 1;
    }
    fclose(cf);

    printf("[+] Loaded %u chunk descriptors from %s\n", num_chunks, chunks_path);

    int dmg_fd = open(dmg_path, O_RDONLY);
    if (dmg_fd < 0) {
        perror("Failed to open DMG");
        free(chunks);
        return 1;
    }

    int out_fd = open(out_path, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (out_fd < 0) {
        perror("Failed to open output image");
        close(dmg_fd);
        free(chunks);
        return 1;
    }

    uint64_t total_sectors = 0;
    for (uint32_t i = 0; i < num_chunks; i++) {
        uint64_t end_sector = chunks[i].sector_num + chunks[i].sector_count;
        if (end_sector > total_sectors) {
            total_sectors = end_sector;
        }
    }
    uint64_t total_bytes = total_sectors * 512;
    printf("[+] Output size will be %llu sectors (%llu bytes, %.2f GB)\n",
           (unsigned long long)total_sectors,
           (unsigned long long)total_bytes,
           (double)total_bytes / (1024.0 * 1024.0 * 1024.0));

    if (ftruncate(out_fd, total_bytes) != 0) {
        perror("ftruncate output failed");
    }

    size_t scratch_size = lzfse_decode_scratch_size();
    void *scratch = malloc(scratch_size ? scratch_size : 1);
    uint8_t *in_buf = malloc(BLOCK_SIZE * 2);
    uint8_t *out_buf = malloc(BLOCK_SIZE * 2);
    uint8_t *zero_buf = calloc(1, BLOCK_SIZE);

    if (!in_buf || !out_buf || !zero_buf) {
        fprintf(stderr, "Failed to allocate memory buffers\n");
        return 1;
    }

    printf("[+] Starting extraction...\n");
    time_t t_start = time(NULL);

    uint64_t decompressed_count = 0;
    uint64_t raw_count = 0;
    uint64_t zero_count = 0;

    for (uint32_t i = 0; i < num_chunks; i++) {
        ChunkDesc *c = &chunks[i];
        if (c->ctype == 0xffffffff) {
            break; // Terminator
        }

        uint64_t out_offset = c->sector_num * 512;
        uint64_t expected_out_len = c->sector_count * 512;

        if (c->ctype == 0x2) {
            // Zero chunk: write zeros in streaming blocks
            uint64_t rem = expected_out_len;
            uint64_t cur = out_offset;
            while (rem > 0) {
                size_t to_write = (rem > BLOCK_SIZE) ? BLOCK_SIZE : (size_t)rem;
                pwrite(out_fd, zero_buf, to_write, cur);
                cur += to_write;
                rem -= to_write;
            }
            zero_count++;
        } else if (c->ctype == 0x1) {
            // Raw chunk: stream in BLOCK_SIZE chunks
            uint64_t rem = c->comp_len;
            uint64_t cur_in = c->comp_off;
            uint64_t cur_out = out_offset;
            while (rem > 0) {
                size_t to_copy = (rem > BLOCK_SIZE) ? BLOCK_SIZE : (size_t)rem;
                ssize_t rd = pread(dmg_fd, in_buf, to_copy, cur_in);
                if (rd != (ssize_t)to_copy) {
                    fprintf(stderr, "[-] Short read on raw chunk %u\n", i);
                    return 1;
                }
                pwrite(out_fd, in_buf, to_copy, cur_out);
                cur_in += to_copy;
                cur_out += to_copy;
                rem -= to_copy;
            }
            raw_count++;
        } else if (c->ctype == 0x80000007) {
            // LZFSE compressed chunk
            if (c->comp_len > BLOCK_SIZE * 2 || expected_out_len > BLOCK_SIZE * 2) {
                fprintf(stderr, "[-] Chunk %u sizes exceed buffer\n", i);
                return 1;
            }
            ssize_t rd = pread(dmg_fd, in_buf, c->comp_len, c->comp_off);
            if (rd != (ssize_t)c->comp_len) {
                fprintf(stderr, "[-] Short read on compressed chunk %u\n", i);
                return 1;
            }
            size_t dec_len = lzfse_decode_buffer(out_buf, expected_out_len, in_buf, c->comp_len, scratch);
            if (dec_len != expected_out_len) {
                fprintf(stderr, "[-] Decompression mismatch on chunk %u: got %zu, expected %llu\n",
                        i, dec_len, (unsigned long long)expected_out_len);
                return 1;
            }
            pwrite(out_fd, out_buf, dec_len, out_offset);
            decompressed_count++;
        } else {
            fprintf(stderr, "[-] Unknown chunk type 0x%x at chunk %u\n", c->ctype, i);
            return 1;
        }

        if ((i + 1) % 250 == 0 || i == num_chunks - 1) {
            double pct = (double)(i + 1) * 100.0 / (double)num_chunks;
            printf("[+] Progress: %u/%u chunks (%.1f%%)\n", i + 1, num_chunks, pct);
            fflush(stdout);
        }
    }

    fsync(out_fd);
    time_t t_end = time(NULL);
    printf("[+] Done in %ld seconds! Decompressed: %llu, Raw: %llu, Zeros: %llu\n",
           (long)(t_end - t_start),
           (unsigned long long)decompressed_count,
           (unsigned long long)raw_count,
           (unsigned long long)zero_count);

    // Verify APFS container superblock magic at offset 0x20
    char magic_check[4] = {0};
    pread(out_fd, magic_check, 4, 0x20);
    if (memcmp(magic_check, "NXSB", 4) == 0) {
        printf("[SUCCESS] APFS Container verified! Magic at offset 0x20 is NXSB!\n");
    } else {
        printf("[WARNING] Offset 0x20 magic check failed: %02x %02x %02x %02x\n",
               (uint8_t)magic_check[0], (uint8_t)magic_check[1], (uint8_t)magic_check[2], (uint8_t)magic_check[3]);
    }

    close(dmg_fd);
    close(out_fd);
    free(chunks);
    free(in_buf);
    free(out_buf);
    free(zero_buf);
    free(scratch);
    return 0;
}

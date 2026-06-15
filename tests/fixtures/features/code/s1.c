int foo()
{
    char *p = malloc(64);
    int n = read(fd, p, 64);
    free(p);
    use(p);
    int x = 0;
    int y = 1;
    return n;
}

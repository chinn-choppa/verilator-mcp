// Deliberately non-terminating simulation; Apache-2.0.
module tb_timeout;
    logic clk = 1'b0;
    always #1 clk = ~clk;
endmodule

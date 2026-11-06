// Self-checking testbench with a per-run acknowledgement token; Apache-2.0.
module tb_good;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic [7:0] count;
    string token;

    counter dut (.clk(clk), .rst_n(rst_n), .count(count));

    always #5 clk = ~clk;
    initial begin
        if (!$value$plusargs("VERILATOR_MCP_TOKEN=%s", token)) begin
            $fatal(1, "missing invocation token");
        end
        #12;
        rst_n = 1'b1;
        repeat (3) @(posedge clk);
        #1;
        if (count !== 8'd3) $fatal(1, "unexpected count %0d", count);
        $display("VERILATOR_MCP_PASS:%s", token);
        $finish;
    end
endmodule
